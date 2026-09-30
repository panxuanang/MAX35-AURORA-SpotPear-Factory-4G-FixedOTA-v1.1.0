#include "aurora_factory_max35_display.h"

#include <cstring>
#include <ctime>
#include <cstdio>
#include <utility>

#include <esp_log.h>
#include <esp_timer.h>

namespace {
constexpr const char* TAG = "AuroraFactoryMAX35";
constexpr uint32_t kIdle = 0x46D7C6;
constexpr uint32_t kListening = 0x55B8FF;
constexpr uint32_t kSpeaking = 0xF2C36B;
constexpr uint32_t kBusy = 0x8EA8FF;
constexpr uint32_t kError = 0xFF6B7A;
constexpr uint32_t kScrollDelayMs = 1700;
constexpr uint32_t kScrollMsPerPixel = 82;
constexpr uint32_t kAfterScrollStayMs = 3200;
constexpr uint32_t kIdleFallbackMs = 30000;

const char* Weekday(int day) {
    static const char* names[] = {
        "星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"
    };
    return (day >= 0 && day < 7) ? names[day] : "";
}

uint32_t StatusColor(const char* status) {
    if (!status) return kIdle;
    if (std::strstr(status, "听") || std::strstr(status, "Listening") || std::strstr(status, "listening")) return kListening;
    if (std::strstr(status, "说") || std::strstr(status, "回答") || std::strstr(status, "Speaking") || std::strstr(status, "speaking")) return kSpeaking;
    if (std::strstr(status, "错") || std::strstr(status, "失败") || std::strstr(status, "Error") || std::strstr(status, "error")) return kError;
    if (std::strstr(status, "连接") || std::strstr(status, "思考") || std::strstr(status, "升级") || std::strstr(status, "Connecting")) return kBusy;
    return kIdle;
}
}  // namespace

void AuroraFactoryMax35Display::SetupUI() {
    LcdDisplay::SetupUI();
    EnsureProductUi();
}

bool AuroraFactoryMax35Display::EnsureProductUi() {
    if (ui_ready_) return true;

#if AURORA_FACTORY_HAS_DISPLAY_LOCK_GUARD
    DisplayLockGuard lock(this);
    if (!lock) return false;
#endif
    if (ui_ready_) return true;

    auto* screen = aurora_factory_max35::ActiveScreen();
    if (!screen) return false;

    aurora_factory_max35::BuildHomeUi(screen, &home_);
    aurora_factory_max35::BuildChatUi(screen, &chat_);
    page_ = Page::Home;
    ShowPageInternal(Page::Home);
    UpdateClockInternal();

    clock_timer_ = lv_timer_create([](lv_timer_t* timer) {
        auto* self = static_cast<AuroraFactoryMax35Display*>(lv_timer_get_user_data(timer));
        if (self && self->ui_ready_ && self->page_ == Page::Home && !self->preview_active_) {
            self->UpdateClockInternal();
        }
    }, 30000, this);

    ui_ready_ = true;
    ESP_LOGI(TAG, "AURORA factory UI attached; vendor MAX35/ML307 stack kept intact");
    return true;
}

void AuroraFactoryMax35Display::ShowPageInternal(Page page) {
    if (!home_.root || !chat_.root) return;
    lv_obj_add_flag(home_.root, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(chat_.root, LV_OBJ_FLAG_HIDDEN);
    auto* target = page == Page::Home ? home_.root : chat_.root;
    aurora_factory_max35::ClearFlag(target, LV_OBJ_FLAG_HIDDEN);
    lv_obj_move_foreground(target);
    page_ = page;
    if (page != Page::Chat) aurora_factory_max35::ChatUiStopScroll(&chat_);
}

void AuroraFactoryMax35Display::SetCustomUiHidden(bool hidden) {
    if (!home_.root || !chat_.root) return;
    if (hidden) {
        lv_obj_add_flag(home_.root, LV_OBJ_FLAG_HIDDEN);
        lv_obj_add_flag(chat_.root, LV_OBJ_FLAG_HIDDEN);
    } else {
        ShowPageInternal(page_);
    }
}

void AuroraFactoryMax35Display::UpdateClockInternal() {
    if (!home_.root) return;
    std::time_t now = std::time(nullptr);
    std::tm tm{};
    localtime_r(&now, &tm);
    char time_text[16] = "--:--";
    char date_text[64] = "时间同步中";
    if (now > 1700000000) {
        std::snprintf(time_text, sizeof(time_text), "%02d:%02d", tm.tm_hour, tm.tm_min);
        std::snprintf(date_text, sizeof(date_text), "%d月%d日  %s", tm.tm_mon + 1, tm.tm_mday, Weekday(tm.tm_wday));
    }
    aurora_factory_max35::HomeUiSetClock(&home_, time_text, date_text);
}

void AuroraFactoryMax35Display::CancelReturnHome() {
    if (!return_timer_) return;
    aurora_factory_max35::DeleteTimer(return_timer_);
    return_timer_ = nullptr;
}

void AuroraFactoryMax35Display::ScheduleReturnHome(uint32_t delay_ms) {
    CancelReturnHome();
    return_timer_ = lv_timer_create([](lv_timer_t* timer) {
        auto* self = static_cast<AuroraFactoryMax35Display*>(lv_timer_get_user_data(timer));
        if (self) {
            self->return_timer_ = nullptr;
            if (!self->preview_active_) {
                self->ShowPageInternal(Page::Home);
                self->UpdateClockInternal();
            }
        }
        aurora_factory_max35::DeleteTimer(timer);
    }, delay_ms, this);
}

#if AURORA_FACTORY_HAS_SET_STATUS
void AuroraFactoryMax35Display::SetStatus(const char* status) {
    LcdDisplay::SetStatus(status);
    if (!EnsureProductUi() || !status || !status[0]) return;
#if AURORA_FACTORY_HAS_DISPLAY_LOCK_GUARD
    DisplayLockGuard lock(this);
    if (!lock) return;
#endif
    const uint32_t color = StatusColor(status);
    if (home_.status) aurora_factory_max35::HomeUiSetState(&home_, status, color, "AI");

    // Enter the dedicated dialog page as soon as the factory firmware reports
    // a listening state, even before ASR text arrives.
    const bool listening = std::strstr(status, "听") ||
                           std::strstr(status, "Listening") ||
                           std::strstr(status, "listening");
    const bool speaking = std::strstr(status, "说") ||
                          std::strstr(status, "回答") ||
                          std::strstr(status, "Speaking") ||
                          std::strstr(status, "speaking");
    const bool idle = std::strstr(status, "待命") ||
                      std::strstr(status, "空闲") ||
                      std::strstr(status, "Idle") ||
                      std::strstr(status, "idle") ||
                      std::strstr(status, "Standby") ||
                      std::strstr(status, "standby");

    if (listening && !preview_active_) {
        CancelReturnHome();
        scroll_finish_us_ = 0;
        if (page_ != Page::Chat) {
            ShowPageInternal(Page::Chat);
            aurora_factory_max35::ChatUiSetUser(&chat_, "正在聆听…");
            aurora_factory_max35::ChatUiSetAnswer(&chat_, "请说，我在听。");
        }
    } else if (speaking && page_ == Page::Chat) {
        // Never leave the answer page while TTS is still speaking.
        CancelReturnHome();
    } else if (idle && page_ == Page::Chat && !preview_active_) {
        const int64_t now = esp_timer_get_time();
        uint32_t delay = kAfterScrollStayMs;
        if (scroll_finish_us_ > now) {
            delay += static_cast<uint32_t>((scroll_finish_us_ - now + 999) / 1000);
        }
        ScheduleReturnHome(delay);
    }
    if (chat_.state && page_ == Page::Chat) aurora_factory_max35::ChatUiSetState(&chat_, status, color);
}
#endif

#if AURORA_FACTORY_HAS_SET_CHAT_MESSAGE
void AuroraFactoryMax35Display::SetChatMessage(const char* role, const char* content) {
    LcdDisplay::SetChatMessage(role, content);
    if (!role || !content || !content[0]) return;
    if (!EnsureProductUi()) return;
#if AURORA_FACTORY_HAS_DISPLAY_LOCK_GUARD
    DisplayLockGuard lock(this);
    if (!lock) return;
#endif
    if (std::strcmp(role, "system") == 0) return;

    CancelReturnHome();
    if (std::strcmp(role, "user") == 0) {
        ShowPageInternal(Page::Chat);
        aurora_factory_max35::ChatUiSetUser(&chat_, content);
        aurora_factory_max35::ChatUiSetAnswer(&chat_, "我听到了，正在思考…");
        aurora_factory_max35::ChatUiSetState(&chat_, "正在思考", kBusy);
        scroll_finish_us_ = 0;
        return;
    }

    if (std::strcmp(role, "assistant") == 0) {
        ShowPageInternal(Page::Chat);
        aurora_factory_max35::ChatUiSetAnswer(&chat_, content);
        aurora_factory_max35::ChatUiSetState(&chat_, "小智正在回答", kSpeaking);
        const uint32_t scroll_ms = aurora_factory_max35::ChatUiStartReadableScroll(&chat_, kScrollDelayMs, kScrollMsPerPixel);
        scroll_finish_us_ = scroll_ms ? (esp_timer_get_time() + static_cast<int64_t>(scroll_ms) * 1000LL) : 0;
        // Normal return-to-home is driven by the factory status becoming idle,
        // so a long TTS response can never disappear early. This fallback only
        // prevents a permanently stuck dialog page if a vendor build never sends
        // an idle status string.
        ScheduleReturnHome(scroll_ms + kIdleFallbackMs);
    }
}
#endif

#if AURORA_FACTORY_HAS_CLEAR_CHAT_MESSAGES
void AuroraFactoryMax35Display::ClearChatMessages() {
    LcdDisplay::ClearChatMessages();
    if (!EnsureProductUi()) return;
#if AURORA_FACTORY_HAS_DISPLAY_LOCK_GUARD
    DisplayLockGuard lock(this);
    if (!lock) return;
#endif
    CancelReturnHome();
    scroll_finish_us_ = 0;
    ShowPageInternal(Page::Chat);
    aurora_factory_max35::ChatUiSetUser(&chat_, "正在聆听…");
    aurora_factory_max35::ChatUiSetAnswer(&chat_, "请说，我在听。");
    aurora_factory_max35::ChatUiSetState(&chat_, "正在聆听", kListening);
}
#endif

#if AURORA_FACTORY_HAS_SET_PREVIEW_IMAGE
void AuroraFactoryMax35Display::SetPreviewImage(std::unique_ptr<LvglImage> image) {
    const bool has_image = static_cast<bool>(image);
    if (has_image && EnsureProductUi()) {
#if AURORA_FACTORY_HAS_DISPLAY_LOCK_GUARD
        DisplayLockGuard lock(this);
        if (lock) {
#endif
            preview_active_ = true;
            CancelReturnHome();
            SetCustomUiHidden(true);
#if AURORA_FACTORY_HAS_DISPLAY_LOCK_GUARD
        }
#endif
    }

    LcdDisplay::SetPreviewImage(std::move(image));

    if (!has_image && EnsureProductUi()) {
#if AURORA_FACTORY_HAS_DISPLAY_LOCK_GUARD
        DisplayLockGuard lock(this);
        if (lock) {
#endif
            preview_active_ = false;
            SetCustomUiHidden(false);
#if AURORA_FACTORY_HAS_DISPLAY_LOCK_GUARD
        }
#endif
    }
}
#endif

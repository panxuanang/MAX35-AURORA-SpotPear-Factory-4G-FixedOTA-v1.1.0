#pragma once

#include "display/lcd_display.h"
#include "aurora_factory_compat.h"
#include "ui_pages.h"

#include <memory>
#include <cstdint>

class AuroraFactoryMax35Display : public SpiLcdDisplay {
public:
    using SpiLcdDisplay::SpiLcdDisplay;

    void SetupUI();
#if AURORA_FACTORY_HAS_SET_STATUS
    void SetStatus(const char* status);
#endif
#if AURORA_FACTORY_HAS_SET_CHAT_MESSAGE
    void SetChatMessage(const char* role, const char* content);
#endif
#if AURORA_FACTORY_HAS_CLEAR_CHAT_MESSAGES
    void ClearChatMessages();
#endif
#if AURORA_FACTORY_HAS_SET_PREVIEW_IMAGE
    void SetPreviewImage(std::unique_ptr<LvglImage> image);
#endif

private:
    enum class Page { Home, Chat };

    aurora_factory_max35::HomeUi home_;
    aurora_factory_max35::ChatUi chat_;
    Page page_ = Page::Home;
    bool ui_ready_ = false;
    bool preview_active_ = false;
    lv_timer_t* clock_timer_ = nullptr;
    lv_timer_t* return_timer_ = nullptr;
    int64_t scroll_finish_us_ = 0;

    bool EnsureProductUi();
    void ShowPageInternal(Page page);
    void SetCustomUiHidden(bool hidden);
    void UpdateClockInternal();
    void CancelReturnHome();
    void ScheduleReturnHome(uint32_t delay_ms);
};

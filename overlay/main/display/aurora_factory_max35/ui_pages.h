#pragma once

#include <cstdint>
#include <lvgl.h>

namespace aurora_factory_max35 {

inline lv_obj_t* ActiveScreen() {
#if LVGL_VERSION_MAJOR >= 9
    return lv_screen_active();
#else
    return lv_scr_act();
#endif
}

inline void ClearFlag(lv_obj_t* obj, lv_obj_flag_t flag) {
#if LVGL_VERSION_MAJOR >= 9
    lv_obj_remove_flag(obj, flag);
#else
    lv_obj_clear_flag(obj, flag);
#endif
}

inline void SetAnimDuration(lv_anim_t* anim, uint32_t ms) {
#if LVGL_VERSION_MAJOR >= 9
    lv_anim_set_duration(anim, ms);
#else
    lv_anim_set_time(anim, ms);
#endif
}

inline void DeleteAnim(void* var) {
#if LVGL_VERSION_MAJOR >= 9
    lv_anim_delete(var, nullptr);
#else
    lv_anim_del(var, nullptr);
#endif
}

inline void DeleteTimer(lv_timer_t* timer) {
    if (!timer) return;
#if LVGL_VERSION_MAJOR >= 9
    lv_timer_delete(timer);
#else
    lv_timer_del(timer);
#endif
}

struct HomeUi {
    lv_obj_t* root = nullptr;
    lv_obj_t* brand = nullptr;
    lv_obj_t* clock = nullptr;
    lv_obj_t* date = nullptr;
    lv_obj_t* orb_outer = nullptr;
    lv_obj_t* orb_mid = nullptr;
    lv_obj_t* orb_core = nullptr;
    lv_obj_t* orb_text = nullptr;
    lv_obj_t* status = nullptr;
    lv_obj_t* hint = nullptr;
};

struct ChatUi {
    lv_obj_t* root = nullptr;
    lv_obj_t* title = nullptr;
    lv_obj_t* state = nullptr;
    lv_obj_t* user_box = nullptr;
    lv_obj_t* user = nullptr;
    lv_obj_t* answer_box = nullptr;
    lv_obj_t* answer = nullptr;
    lv_obj_t* footer = nullptr;
};

void BuildHomeUi(lv_obj_t* screen, HomeUi* ui);
void HomeUiSetClock(HomeUi* ui, const char* time_text, const char* date_text);
void HomeUiSetState(HomeUi* ui, const char* text, uint32_t color, const char* orb_text = "AI");

void BuildChatUi(lv_obj_t* screen, ChatUi* ui);
void ChatUiSetUser(ChatUi* ui, const char* text);
void ChatUiSetAnswer(ChatUi* ui, const char* text);
void ChatUiSetState(ChatUi* ui, const char* text, uint32_t color);
void ChatUiStopScroll(ChatUi* ui);
uint32_t ChatUiStartReadableScroll(ChatUi* ui, uint32_t delay_ms, uint32_t ms_per_pixel);

}  // namespace aurora_factory_max35

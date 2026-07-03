#pragma once

#include <SDL2/SDL_video.h>

#include "ZunResult.hpp"
#include "graphics/GfxInterface.hpp"
#include "inttypes.hpp"

// The internal resolution EoSD uses. 640x480. I can't think of any reason anyone sane
//   would want to change this
#define GAME_WINDOW_WIDTH (640)
#define GAME_WINDOW_HEIGHT (480)

// The actual resolution used for the output window and viewport scaling.
// These are now runtime variables so the window can be resized and fullscreen
// can use the desktop resolution without changing the display mode.
extern i32 g_GameWindowWidthReal;
extern i32 g_GameWindowHeightReal;

// Cached viewport dimensions and scaling factors, updated whenever the window size changes
extern u32 g_ViewportWidth;
extern u32 g_ViewportOffsetX;
extern u32 g_ViewportHeight;
extern u32 g_ViewportOffsetY;
extern f32 g_WidthResolutionScale;
extern f32 g_HeightResolutionScale;

// Macro aliases for backward compatibility (they expand to runtime globals)
#define GAME_WINDOW_WIDTH_REAL  g_GameWindowWidthReal
#define GAME_WINDOW_HEIGHT_REAL g_GameWindowHeightReal
#define VIEWPORT_WIDTH          g_ViewportWidth
#define VIEWPORT_OFF_X          g_ViewportOffsetX
#define VIEWPORT_HEIGHT         g_ViewportHeight
#define VIEWPORT_OFF_Y          g_ViewportOffsetY
#define WIDTH_RESOLUTION_SCALE  g_WidthResolutionScale
#define HEIGHT_RESOLUTION_SCALE g_HeightResolutionScale

// Call this whenever the window size changes (creation, resize, fullscreen toggle)
void UpdateViewportDimensions();

enum RenderResult
{
    RENDER_RESULT_KEEP_RUNNING,
    RENDER_RESULT_EXIT_SUCCESS,
    RENDER_RESULT_EXIT_ERROR,
};

struct GameWindow
{
    RenderResult Render();
    static void Present();

    static void CreateGameWindow();
    static ZunResult InitD3dRendering();
    static void InitD3dDevice();

    i32 isAppClosing;
    i32 lastActiveAppValue;
    i32 isAppActive;
    u8 curFrame;
    i32 screenSaveActive;
    i32 lowPowerActive;
    i32 powerOffActive;
    u32 renderBackendIndex;
};

extern GameWindow g_GameWindow;
extern i32 g_TickCountToEffectiveFramerate;
extern double g_LastFrameTime;
extern GfxInterface *g_GfxBackend;
extern SDL_Window *g_SdlWindow;
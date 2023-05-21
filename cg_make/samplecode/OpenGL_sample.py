"""
OpenGL Pointcloud viewer with http://pyglet.org

Usage:
------
Mouse:
    Drag with left button to rotate around pivot (thick small axes),
    with right button to translate and the wheel to zoom.

Keyboard:
    [f1]    Toggle full screen
    [f2]    Switch full screen
    [a]     Toggle axis, frustrum, grid
    [b]     Toggle chessbord
    [g]     Toggle drawing grid floor
    [p]     Pause
    [r]     Reset View
    [s]     Save PNG (./out.png)
    [→]     increase delta_zNear to zoom
    [←]     dencrease delta_zNear to zoom
    [↑]     unzoom by increasing zNear (by delta_zNear)
    [↓]     zoom by increasing zNear (by delta_zNear)
    [q/ESC] Quit

"""

import os
import math
import numpy as np
import cv2

from PIL import Image
import pyglet
import pyglet.gl as gl

import ctypes

#===============================
# 定数
#===============================

TARGET_SCREEN_ID = 0     # プロジェクタのスクリーンID

DATA_DIRNAME = "data"
DATA_DIRPATH = os.path.join(os.path.dirname(__file__), DATA_DIRNAME)
if not os.path.exists(DATA_DIRPATH):
    os.makedirs(DATA_DIRPATH)

CHESS_HNUM = 7       # 水平方向個数
CHESS_VNUM = 10      # 垂直方向個数
CHESS_MARGIN = 50    # [px]
CHESS_BLOCKSIZE = 80 # [px]

BOARD_WIDTH  = 0.33  # chessboard の横幅 [m]
BOARD_HEIGHT = 0.45  # chessboard の縦幅 [m]
BOARD_X = 0.         # chessboard の3次元位置X座標 [m]（右手系）
BOARD_Y = 0.         # chessboard の3次元位置Y座標 [m]（右手系）
BOARD_Z = -3.0       # chessboard の3次元位置Z座標 [m]（右手系）[see]


# OpenGL の射影のパラメータ
class Params:
    def __init__(self, zNear = 0.0001, zFar = 20.0, fovy = 20.0):
        self.Z_NEAR = zNear     # 最も近い点 [m]
        self.Z_FAR  = zFar      # 最も遠い点 [m]
        self.FOVY   = fovy      # 縦の視野角 [deg]


PARAMS = Params(zNear = 0.0001, # [m]
                zFar = 20.0,    # [m]
                fovy = 20.0     # [deg]
                )

#===============================
# グローバル変数
#===============================
window = None        # pyglet の Window　クラスのインスタンス
state = None         # アプリの状態を管理する変数（AppState）
cam_w, cam_h  = 0, 0 # 画面解像度

# ボードのテクスチャ
board_texture = None
chessboard_data = None

# ボードの位置
board_vertices = ((BOARD_X - BOARD_WIDTH / 2, BOARD_Y + BOARD_HEIGHT, BOARD_Z),
                  (BOARD_X - BOARD_WIDTH / 2, BOARD_Y, BOARD_Z),
                  (BOARD_X + BOARD_WIDTH / 2, BOARD_Y, BOARD_Z),
                  (BOARD_X + BOARD_WIDTH / 2, BOARD_Y + BOARD_HEIGHT, BOARD_Z))

#===============================
# 状態変数
#===============================
class AppState:
    def __init__(self, params):
        self.params = params
        self.zNear = self.params.Z_NEAR
        self.delta_zNear = 0.001

        self.roll = math.radians(0)
        self.pitch = math.radians(0)
        self.yaw = math.radians(0)
        self.trans = np.array([0, 0, 0], np.float32)
        self.rvec = np.array([0, 0, 0], np.float32)
        self.tvec = np.array([0, 0, 0], np.float32)

        # 描画時の状態変数
        self.mouse_btns = [False, False, False]
        self.draw_axes = False
        self.draw_grid = False
        self.draw_board = True
        self.half_fov = False                  # プロジェクタの画角の変数

    def reset(self):
        self.zNear = self.params.Z_NEAR
        self.roll, self.pitch, self.yaw = 0, 0, 0
        self.trans[:] = 0, 0, 0
        self.rvec[:] = np.array([0, 0, 0], np.float32)

#===============================
# 回転に関する関数
#===============================
# 外因性オイラー角でのロール・ピッチ・ヨーから回転行列への変換
def rotation_matrix_rpy_euler(roll, pitch, yaw):
    sr = np.sin(roll)
    sp = np.sin(pitch)
    sy = np.sin(yaw)
    cr = np.cos(roll)
    cp = np.cos(pitch)
    cy = np.cos(yaw)

    rm = (gl.GLfloat * 16)()
    rm[0] = sp*sr*sy + cr*cy
    rm[1] = sr*cp
    rm[2] = sp*sr*cy - sy*cr
    rm[3] = 0
    rm[4] = sp*sy*cr - sr*cy
    rm[5] = cp*cr
    rm[6] = sp*cr*cy + sr*sy
    rm[7] = 0
    rm[8] = sy*cp
    rm[9] = -sp
    rm[10] = cp*cy
    rm[11] = 0
    rm[12] = 0
    rm[13] = 0
    rm[14] = 0
    rm[15] = 1
    return rm

#===============================
# 関数群
#===============================
# copy our data to pre-allocated buffers, this is faster than assigning...
# pyglet will take care of uploading to GPU
def copy(dst, src):
    """copy numpy array to pyglet array"""
    # timeit was mostly inconclusive, favoring slice assignment for safety
    np.array(dst, copy=False)[:] = src.ravel()

def make_chessboard(num_h, num_v, margin, block_size):
    chessboard = np.ones((block_size * num_v + margin * 2, block_size * num_h + margin * 2, 3), dtype=np.uint8) * 255

    for y in range(num_v):
        for x in range(num_h):
            if (x + y) % 2 == 0:
                sx = x * block_size + margin
                sy = y * block_size + margin
                chessboard[sy:sy + block_size, sx:sx + block_size, 0] = 0
                chessboard[sy:sy + block_size, sx:sx + block_size, 1] = 0
                chessboard[sy:sy + block_size, sx:sx + block_size, 2] = 0

    return chessboard

def load_chessboard():
    global chessboard_image, texture_ids

    chessboard = make_chessboard(CHESS_HNUM, CHESS_VNUM, CHESS_MARGIN, CHESS_BLOCKSIZE)

    filepath = os.path.join(DATA_DIRPATH, 'chessboard.png')
    cv2.imwrite(filepath, chessboard)
    chessboard_image = Image.open(filepath)
    chessboard_image = Image.open("data/lenna.png")

    tw, th = chessboard_image.width, chessboard_image.height
    gl.glBindTexture(gl.GL_TEXTURE_2D, texture_ids[0])
    gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGB, tw, th, 0, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, chessboard_image.tobytes())

# def load_png():
#     global chessboard_image, texture_ids

#     chessboard = make_chessboard(CHESS_HNUM, CHESS_VNUM, CHESS_MARGIN, CHESS_BLOCKSIZE)

#     filepath = os.path.join(DATA_DIRPATH, 'lenna.png')
#     cv2.imwrite(filepath, chessboard)
#     chessboard_image = Image.open(filepath)

#     tw, th = chessboard_image.width, chessboard_image.height
#     gl.glBindTexture(gl.GL_TEXTURE_2D, texture_ids[0])
#     gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGB, tw, th, 0, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, chessboard_image.tobytes())


#-------------------------------
# 描画関数
#-------------------------------
def axes(size=1, width=1):
    gl.glMatrixMode(gl.GL_MODELVIEW)

    """draw 3d axes"""
    gl.glLineWidth(width)
    pyglet.graphics.draw(6, gl.GL_LINES,
                         ('v3f', (0, 0, 0, size, 0, 0,
                                  0, 0, 0, 0, size, 0,
                                  0, 0, 0, 0, 0, size)),
                         ('c3f', (1, 0, 0, 1, 0, 0,
                                  0, 1, 0, 0, 1, 0,
                                  0, 0, 1, 0, 0, 1,
                                  ))
                         )


# 地面のグリッドの描画
def grid(size=1, n=10, width=1):
    gl.glMatrixMode(gl.GL_MODELVIEW)

    """draw a grid on xz plane"""
    gl.glLineWidth(width)
    s = size / float(n)
    s2 = 0.5 * size
    batch = pyglet.graphics.Batch()

    for i in range(0, n + 1):
        x = -s2 + i * s
        batch.add(2, gl.GL_LINES, None, ('v3f', (x, 0, -s2, x, 0, s2)))
    for i in range(0, n + 1):
        z = -s2 + i * s
        batch.add(2, gl.GL_LINES, None, ('v3f', (-s2, 0, z, s2, 0, z)))

    batch.draw()

def board():
    global chessboard_image, texture_ids

    gl.glMatrixMode(gl.GL_MODELVIEW)

    gl.glEnable(gl.GL_TEXTURE_2D)
    gl.glBindTexture(gl.GL_TEXTURE_2D, texture_ids[0])
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
    gl.glTexEnvi(gl.GL_TEXTURE_ENV, gl.GL_TEXTURE_ENV_MODE, gl.GL_REPLACE)

    gl.glMatrixMode(gl.GL_TEXTURE)
    gl.glPushMatrix()
    gl.glLoadIdentity()
    gl.glTranslatef(0.5 / chessboard_image.width, 0.5 / chessboard_image.height, 0)

    gl.glBegin(gl.GL_QUADS)
    gl.glTexCoord2i(0, 0)
    gl.glVertex3f(*board_vertices[0])
    gl.glTexCoord2i(0, 1)
    gl.glVertex3f(*board_vertices[1])
    gl.glTexCoord2i(1, 1)
    gl.glVertex3f(*board_vertices[2])
    gl.glTexCoord2i(1, 0)
    gl.glVertex3f(*board_vertices[3])
    gl.glEnd()
    gl.glPopMatrix()

    gl.glDisable(gl.GL_TEXTURE_2D)


#-------------------------------
# ここからイベント関数
#-------------------------------
def on_mouse_drag_impl(x, y, dx, dy, buttons, modifiers):
    cam_w, cam_h = map(float, window.get_size())

    if buttons & pyglet.window.mouse.LEFT:
        state.yaw -= dx * 0.001
        state.pitch += dy * 0.001

    if buttons & pyglet.window.mouse.RIGHT:
        # dp = np.array((dx / cam_w, -dy / cam_h, 0), np.float32)
        # state.translation += np.dot(state.rotation, dp)
        state.trans += np.array((dx, dy, 0)) * 0.002

    if buttons & pyglet.window.mouse.MIDDLE:
        state.roll -= dx * 0.001

def on_mouse_button_impl(x, y, button, modifiers):
    state.mouse_btns[0] ^= (button & pyglet.window.mouse.LEFT)
    state.mouse_btns[1] ^= (button & pyglet.window.mouse.RIGHT)
    state.mouse_btns[2] ^= (button & pyglet.window.mouse.MIDDLE)


def on_mouse_scroll_impl(x, y, scroll_x, scroll_y):
    dz = scroll_y * 0.1
    state.trans[2] += dz

# [key]
def on_key_press_impl(symbol, modifiers):
    if symbol == pyglet.window.key.F1:
        state.draw_axes = False
        state.draw_grid = False

    # フルスクリーン/ウインドウ表示切り替え
    if symbol == pyglet.window.key.F2:
        if not window.fullscreen:
            # フルスクリーン表示に設定
            window.set_fullscreen(fullscreen=True)
        else:
            # ウインドウ表示に設定
            window.set_fullscreen(fullscreen=False)

    if symbol == pyglet.window.key.A:
        state.draw_axes ^= True
        state.draw_grid ^= True

    if symbol == pyglet.window.key.B:
        state.draw_board ^= True

    if symbol == pyglet.window.key.F:
        state.half_fov ^=True

    if symbol == pyglet.window.key.G:
        state.draw_grid ^= True

    if symbol == pyglet.window.key.Q:
        window.close()

    if symbol == pyglet.window.key.R:
        state.reset()

    if symbol == pyglet.window.key.UP:
        state.zNear += state.delta_zNear
        print("current zNear = ", state.zNear)

    if symbol == pyglet.window.key.DOWN:
        state.zNear -= state.delta_zNear
        while state.zNear < 0:
            state.zNear += state.delta_zNear
        print("current zNear = ", state.zNear)

    if symbol == pyglet.window.key.RIGHT:
        state.delta_zNear *= 2
        print("current delta_zNear = ", state.delta_zNear)

    if symbol == pyglet.window.key.LEFT:
        state.delta_zNear /= 2
        print("current delta_zNear = ", state.delta_zNear)


#-------------------------------
# ここから座標変換用の関数
#-------------------------------
def projection():
    width, height = window.get_size()
    gl.glViewport(0, 0, width, height)
    fov = PARAMS.FOVY*0.5

    # 射影行列の設定
    gl.glMatrixMode(gl.GL_PROJECTION)
    gl.glLoadIdentity()

    aspect = width / float(height)
    top = state.zNear * np.tan(np.radians(fov))
    bottom = -state.zNear * np.tan(np.radians(fov))
    left = - top * aspect
    right = top * aspect

    pm = (gl.GLfloat * 16)()
    if state.half_fov: #
        pm[0] = 4 * state.zNear / (right - left)
        pm[5] = 4 * state.zNear / (top - bottom)
        pm[8] = (right + left) / (right - left)
        pm[9] = 1 + 2 * (top + bottom) / (top - bottom)
        pm[10] = - (PARAMS.Z_FAR + state.zNear) / (PARAMS.Z_FAR - state.zNear)
        pm[11] = - 1
        pm[14] = - 2 * PARAMS.Z_FAR * state.zNear / (PARAMS.Z_FAR - state.zNear)
    else:
        pm[0] = 2 * state.zNear / (right - left)
        pm[5] = 2 * state.zNear / (top - bottom)
        pm[8] = (right + left) / (right - left)
        pm[9] = (top + bottom) / (top - bottom)
        pm[10] = - (PARAMS.Z_FAR + state.zNear) / (PARAMS.Z_FAR - state.zNear)
        pm[11] = - 1
        pm[14] = - 2 * PARAMS.Z_FAR * state.zNear / (PARAMS.Z_FAR - state.zNear)
    gl.glLoadMatrixf((ctypes.c_float * 16)(*pm))

def modelview():
    gl.glMatrixMode(gl.GL_MODELVIEW)

    gl.glLoadIdentity()

    _matrix = rotation_matrix_rpy_euler(state.roll, state.pitch, state.yaw)
    _matrix[12] = state.tvec[0]
    _matrix[13] = state.tvec[1]
    _matrix[14] = state.tvec[2]
    _matrix[15] = 1
    gl.glLoadMatrixf((ctypes.c_float * 16)(*_matrix))

    # gluLookAt( float eyeX, float eyeY, float eyeZ,
    #            float centerX, float centerY, float centerZ,
    #            float upX, float upY, float upX
    # )
    gl.gluLookAt(0.0, 0.0, 0.0,
                 0.0, 0.0, -1.0,
                 0.0, 1.0, 0.0)

    #-------------------------------------
    # numpy 配列への変換
    mm = (gl.GLfloat * 16)()
    gl.glGetFloatv(gl.GL_MODELVIEW_MATRIX, mm)
    modelview_matrix = np.array(mm).reshape(4, 4).transpose()

    #-------------------------------------
    # 回転ベクトルへの変換
    R = modelview_matrix[0:3, 0:3]
    rvec, _ = cv2.Rodrigues(R)
    state.rvec = rvec.reshape(3)


#-------------------------------
# ここから描画関数
#-------------------------------

def on_draw_impl():
    window.clear()

    gl.glClearColor(0, 0, 0, 1)

    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_LINE_SMOOTH)

    projection()
    modelview()

    #====================================================
    if state.draw_board:
        board()

    # カメラ座標軸の描画
    if state.draw_axes and any(state.mouse_btns):
        axes(0.1, 4)

    # 地面の格子の描画
    if state.draw_grid:
        gl.glColor3f(0.5, 0.5, 0.5)
        grid()

    if state.draw_axes:
        gl.glColor3f(0.25, 0.25, 0.25)
        axes()
    #====================================================

#-------------------------------
# ここからがメイン部分
#-------------------------------
# メインの処理
if __name__ == '__main__':

    # アプリクラスのインスタンス
    state = AppState(PARAMS)

    #-------------------------------
    # ここから描画準備：Pyglet
    #-------------------------------
    display = pyglet.canvas.get_display()
    screens = display.get_screens()
    target_screen_id = TARGET_SCREEN_ID
    target_screen = screens[target_screen_id]  # ここで投影対象画面を変更
    config = gl.Config(
        double_buffer=True,
        sample_buffers=1,
        samples=4,  # MSAA
        depth_size=24,
        alpha_size=8
    )
    config = target_screen.get_best_config(config)
    window = pyglet.window.Window(
        config=config,
        resizable=True,
        vsync=False,
        fullscreen=True,
        screen=target_screen)

    @window.event
    def on_draw():
        on_draw_impl()

    @window.event
    def on_key_press(symbol, modifiers):
        on_key_press_impl(symbol, modifiers)

    @window.event
    def on_mouse_drag(x, y, dx, dy, buttons, modifiers):
        on_mouse_drag_impl(x, y, dx, dy, buttons, modifiers)

    @window.event
    def on_mouse_scroll(x, y, scroll_x, scroll_y):
        on_mouse_scroll_impl(x, y, scroll_x, scroll_y)

    @window.event
    def on_mouse_press(x, y, button, modifiers):
        on_mouse_button_impl(x, y, button, modifiers)

    @window.event
    def on_mouse_release(x, y, button, modifiers):
        on_mouse_button_impl(x, y, button, modifiers)

    #------------------------------
    # OpenGL 用の変数の準備
    #------------------------------
    # チェスボードの作成
    texture_ids = (pyglet.gl.GLuint * 1)()
    gl.glGenTextures(1, texture_ids)
    load_chessboard()

    # Start
    pyglet.app.run()


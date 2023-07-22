import pyglet
from pyglet.gl import *
from PIL import Image

def resize_texture(texture, new_width, new_height):
    # Get the pixel data from the original texture
    glBindTexture(texture.target, texture.id)
    pixel_data = glGetTexImage(GL_TEXTURE_2D, 0, GL_RGBA, GL_UNSIGNED_BYTE)

    # Create a new texture with the new size
    new_texture_id = GLuint(0)
    glGenTextures(1, new_texture_id)
    glBindTexture(GL_TEXTURE_2D, new_texture_id)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, new_width, new_height, 0, GL_RGBA, GL_UNSIGNED_BYTE, pixel_data)

    return new_texture_id

def load_texture(filename):
    image = Image.open(filename)
    image_data = image.tobytes("raw", "RGB", 0, -1)
    width, height = image.size

    texture_id = GLuint(0)
    glGenTextures(1, texture_id)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, width, height, 0, GL_RGB, GL_UNSIGNED_BYTE, image_data)

    return texture_id, width, height

# Window dimensions
WIDTH, HEIGHT = 1200, 1000

# Load textures
texture1_id, texture1_width, texture1_height = load_texture('data/back.JPG')
texture2_id, texture2_width, texture2_height = load_texture('data/wolf.png')

# Create vertex list for quad
vertex_list_back = pyglet.graphics.vertex_list(4,
    ('v2f', [0, 0, WIDTH, 0, WIDTH, HEIGHT, 0, HEIGHT]),
    ('t2f', [0, 0, 1, 0, 1, 1, 0, 1])
)
WIDTH, HEIGHT = 200, 200
vertex_list_front = pyglet.graphics.vertex_list(4,
    ('v2f', [0, 0, WIDTH, 0, WIDTH, HEIGHT, 0, HEIGHT]),
    ('t2f', [0, 0, 1, 0, 1, 1, 0, 1])
)

# Initial positions
texture1_x = 0
texture1_y = 0
texture2_x = 100
texture2_y = 100

# Create window
window = pyglet.window.Window(WIDTH, HEIGHT, resizable=True)

@window.event
def on_draw():
    window.clear()

    glEnable(GL_TEXTURE_2D)

    # Bind and draw texture1
    glBindTexture(GL_TEXTURE_2D, texture1_id)
    glPushMatrix()
    glTranslatef(texture1_x, texture1_y, 0)
    vertex_list_back.draw(GL_QUADS)
    glPopMatrix()

    # Bind and draw texture2 overlaid on texture1
    glBindTexture(GL_TEXTURE_2D, texture2_id)
    glPushMatrix()
    glTranslatef(texture2_x, texture2_y, 0)
    vertex_list_front.draw(GL_QUADS)
    glPopMatrix()

    glDisable(GL_TEXTURE_2D)

@window.event
def on_resize(width, height):
    glViewport(0, 0, width, height)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    glOrtho(0, width, 0, height, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    return pyglet.event.EVENT_HANDLED

@window.event
def on_mouse_drag(x, y, dx, dy, buttons, modifiers):
    global texture1_x, texture1_y, texture2_x, texture2_y
    if buttons & pyglet.window.mouse.RIGHT:
        texture1_x += dx
        texture1_y += dy
    if buttons & pyglet.window.mouse.LEFT:
        texture2_x += dx
        texture2_y += dy

pyglet.app.run()

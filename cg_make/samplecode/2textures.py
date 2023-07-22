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

    # Create a new TextureRegion using the new texture
    new_texture = pyglet.image.Texture(new_width, new_height, texture.format, id=new_texture_id)
    new_texture_region = new_texture.get_region(0, 0, new_width, new_height)

    return new_texture_region


# Window dimensions
WIDTH, HEIGHT = 1200, 1000

tex2 = Image.open('data/wolf.png')
width, height = 100, 100
tex2_resized = tex2.resize((width, height))
# Load textures
texture1 = pyglet.image.load('data/back.JPG').get_texture()
texture2 = pyglet.image.load('data/wolf.png').get_texture()

# Resize texture
# width = 10  # Desired width
# height = 20  # Desired height
# texture2 = texture2.get_region(0, 0, width, height)

# Resize texture2 to new width and height
new_width = 200
new_height = 200
texture2 = resize_texture(texture2, new_width, new_height)
print(type(texture2))

# Create vertex list for quad
vertex_list = pyglet.graphics.vertex_list(4,
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
    glBindTexture(texture1.target, texture1.id)
    glPushMatrix()
    glTranslatef(texture1_x, texture1_y, 0)
    vertex_list.draw(GL_QUADS)
    glPopMatrix()
    
    # Bind and draw texture2 overlaid on texture1
    glBindTexture(texture2.target, texture2.id)
    glPushMatrix()
    glTranslatef(texture2_x, texture2_y, 0)
    vertex_list.draw(GL_QUADS)
    glPopMatrix()

    glDisable(GL_TEXTURE_2D)

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

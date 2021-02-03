import pylast
import cairo
import tkinter
from math import ceil,sin,cos,pi
import random
import os



#region Parameters
WIDTH, HEIGHT = 2000, 1000 
LIMIT = 30 
PERIOD = pylast.PERIOD_1MONTH
MAX_FONT_SIZE = 150
MIN_FONT_SIZE = 30
BASE = 1.1
STEPSIZE = pi/200
CURVE_MULTIPLIER = 1

#endregion
#region LastFM stuff
API_KEY = os.environ.get("LASTFM_API_KEY")
API_SECRET = os.environ.get("LASTFM_API_SECRET")

network = pylast.LastFMNetwork(
    api_key=API_KEY,
    api_secret=API_SECRET,
)
#endregion 

def get_spiral_coords(theta):
    x = ceil(CURVE_MULTIPLIER *theta * cos(theta)) + WIDTH / 2
    y = ceil(CURVE_MULTIPLIER*theta * sin(theta)) + HEIGHT / 2
    return x,y

def choose_colour():
    # All colours must be atleast 0.5 to stop looking too dark
    while True:
        r = random.uniform(0.4,1)
        g = random.uniform(0.4,1)
        b = random.uniform(0.4,1)    
        # However, we dont want to be pure white, or near to it, so we max the sum to 2 (out of a maximum of 3).
        if (r+g+b) < 2:
            break
    return r,g,b

#region artists processing
artists_raw = network.get_user("ndewy").get_top_artists(period=PERIOD,limit=LIMIT)
#Turn this into an array of artists sorted by plays
artists = []
for artist in artists_raw:
    artists.append(str(artist.item))

# Make font sizes follow negative exponential curve with base BASE
artist_sizes =[]

for i,artist in enumerate(artists):
        size = ceil(MAX_FONT_SIZE/(BASE**i))
        if size<=MIN_FONT_SIZE:
            size = MIN_FONT_SIZE
        artist_sizes.append((size,artist))
#endregion

#region Cairo Image processing
surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)
ctx = cairo.Context(surface)
ctx.rectangle(0, 0, WIDTH, HEIGHT)
ctx.set_source_rgb(1, 1, 1)
ctx.fill()
ctx.set_source_rgb(0, 0, 0)
ctx.set_font_size(200)
ctx.select_font_face("Arial", cairo.FONT_SLANT_NORMAL, 
    cairo.FONT_WEIGHT_NORMAL)

#Generate text extents
text_extents = []
for font_size,artist in artist_sizes:
    ctx.set_font_size(font_size)
    text_extents.append(ctx.text_extents(artist))

rectangles= []
for i,(font_size,artist) in enumerate(artist_sizes):
    theta = random.randint(0,300) # Choose a random start position
    print(artist + "   " + str(font_size))
    extent = text_extents[i]
    
    good_position = False # you cannot have a good position until you are colliding with nothing.
    while not good_position:
        #Collision Detection
        ax1,ay2 = get_spiral_coords(theta) #We get the bottom left corner, so ay2 as y goes down here
        ax2 = ax1 + extent.width
        ay1 = ay2 - extent.height
        #First item will have no rectangles to compare against.
        if i==0:
            good_position=True
        for j in range(0,len(rectangles)):
            bx1 = rectangles[j][0]
            bx2 = rectangles[j][1]
            by1 = rectangles[j][2]
            by2 = rectangles[j][3]

            x_colliding = ( bx1 <= ax1 and ax1 <= bx2) or (bx1 <= ax2 and ax2 <= bx2) or ( ax1 <= bx1 and bx1 <= ax2) or (ax1 <= bx2 and bx2 <= ax2)
            y_colliding = (by1 <= ay1 and ay1 <= by2) or (by1 <= ay2 and ay2 <= by2) or (ay1 <= by1 and by1 <= ay2) or (ay1 <= by2 and by2 <= ay2)

            if x_colliding and y_colliding:
                good_position = False
                break
            good_position = True

        #Move a bit
        if not good_position:
            theta += STEPSIZE

    #Draw Text
    x,y = get_spiral_coords(theta)
    ctx.move_to(x,y)
    ctx.set_font_size(font_size)
    r,g,b = choose_colour()
    ctx.set_source_rgb(r, g, b)
    ctx.show_text(artist)
    #Add rectangle to rectangles
    rectangles.append((x,x+extent.width,y-extent.height,y))

surface.write_to_png("image.png")  # Output to PNG
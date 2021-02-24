import io
import os
import random
import threading
import tkinter as tk
import tkinter.messagebox as messagebox
from math import ceil, cos, pi, sin

import cairo
import pylast
from PIL import Image, ImageTk

# Use me to convert from index in selection box to actual time periods
TIME_PERIODS = {"All Time": pylast.PERIOD_OVERALL,
                "Last Week": pylast.PERIOD_7DAYS,
                "Last Month": pylast.PERIOD_1MONTH,
                "Last 3 Months": pylast.PERIOD_3MONTHS,
                "Last 6 months": pylast.PERIOD_6MONTHS,
                "Last Year": pylast.PERIOD_12MONTHS}


class ImageWindow(tk.Toplevel):
    def __init__(self, image, master=None):
        super().__init__(master)
        self.resizable(width=False, height=False)
        self.image = image
        thumbnail = image.copy()
        thumbnail.thumbnail((500, 500))
        self.tkimage = ImageTk.PhotoImage(thumbnail)
        self.master = master
        self.create_widgets()

    def create_widgets(self):
        self.label = tk.Label(self, image=self.tkimage)
        # self.label.bind('<Configure>', self.resize)
        self.label.pack()

    def report_callback_exception(self, *args):
        self.destroy()

    def resize(self, event):
        new_width = self.winfo_width()
        new_height = self.winfo_height()
        self.tkimage = ImageTk.PhotoImage(self.image.resize(
            (new_width, new_height)))
        self.label.config(image=self.tkimage)
        self.label.image = self.tkimage


class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.master.title("LastFM")
        self.pack()
        self.create_widgets()

        self.master.resizable(width=False, height=False)

    def create_widgets(self):
        self.options = {}

        self.options["time"] = tk.StringVar()
        time_label = tk.Label(self, text="Time period:")
        time_menu = tk.OptionMenu(self, self.options["time"],
                                  *TIME_PERIODS.keys())
        self.options["time"].set('All Time')

        self.options["type"] = tk.StringVar()
        type_label = tk.Label(self, text="Select Graph type:")
        type_menu = tk.OptionMenu(self, self.options["type"], "Artist", "Song")
        self.options["type"].set("Artist")

        create = tk.Button(self)
        create["text"] = "Create"
        create["command"] = self.generate

        self.options["limit"] = tk.StringVar()
        self.validate = self.master.register(self.integer_validate)
        limit_input = tk.Entry(self, textvariable=self.options["limit"],
                               validatecommand=(self.validate, '%S'),
                               validate='key')
        limit_input.insert(0, "20")
        limit_label = tk.Label(self, text="Limit:")

        self.options["user"] = tk.StringVar()
        users_label = tk.Label(self, text="Username:")
        self.options["user"].set("ndewy")
        users_input = tk.Entry(self, textvariable=self.options["user"])

        time_label.grid(column=0, row=0)
        time_menu.grid(column=1, row=0)
        type_label.grid(column=0, row=1)
        type_menu.grid(column=1, row=1)
        limit_label.grid(column=0, row=2)
        limit_input.grid(column=1, row=2)
        users_label.grid(column=0, row=3)
        users_input.grid(column=1, row=3)
        create.grid(column=2, row=4)

    def generate(self):
        params = {}
        params["time"] = TIME_PERIODS[self.options["time"].get()]
        params["user"] = self.options["user"].get()
        if self.options["limit"].get() == "":
            params["limit"] = 10
        else:
            params["limit"] = int(self.options["limit"].get())
        t = threading.Thread(target=generate,
                             args=(self.on_generated,
                                   self.on_generating_fail, params))
        t.start()

    def on_generated(self, image_path):
        ImageWindow(image_path, master=self)

    def on_generating_fail(self, msg):
        messagebox.showerror("Generation Failed", str(msg))

    def integer_validate(self, char):
        return char.isdigit()


# region Parameters
WIDTH, HEIGHT = 2000, 1000
MAX_FONT_SIZE = 150
MIN_FONT_SIZE = 30
BASE = 1.1
STEPSIZE = pi/200
CURVE_MULTIPLIER = 1

# endregion
# region LastFM stuff
API_KEY = os.environ.get("LASTFM_API_KEY")
API_SECRET = os.environ.get("LASTFM_API_SECRET")

network = pylast.LastFMNetwork(
    api_key=API_KEY,
    api_secret=API_SECRET,
)
# endregion


def get_spiral_coords(theta):
    x = ceil(CURVE_MULTIPLIER * theta * cos(theta)) + WIDTH / 2
    y = ceil(CURVE_MULTIPLIER * theta * sin(theta)) + HEIGHT / 2
    return x, y


def choose_colour():
    # All colours must be atleast 0.5 to stop looking too dark
    while True:
        r = random.uniform(0.4, 1)
        g = random.uniform(0.4, 1)
        b = random.uniform(0.4, 1)
        # However, we dont want to be pure white, or near to it, so we max the
        # sum to 2 (out of a maximum of 3).
        if (r+g+b) < 2:
            break
    return r, g, b


def generate(callback_success, callback_fail, parameters):
    ''' Generates wordle'''
    # region artists processing
    try:
        artists_raw = network.get_user(parameters["user"]).get_top_artists(
         period=parameters["time"], limit=parameters["limit"])
    except pylast.WSError as e:
        callback_fail(e)
        return
    # Turn this into an array of artists sorted by plays
    artists = []
    for artist in artists_raw:
        artists.append(str(artist.item))

    # Make font sizes follow negative exponential curve with base BASE
    artist_sizes = []

    for i, artist in enumerate(artists):
        size = ceil(MAX_FONT_SIZE/(BASE**i))
        if size <= MIN_FONT_SIZE:
            size = MIN_FONT_SIZE
        artist_sizes.append((size, artist))
    # endregion

    # region Cairo Image processing
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)
    ctx = cairo.Context(surface)
    ctx.rectangle(0, 0, WIDTH, HEIGHT)
    ctx.set_source_rgb(1, 1, 1)
    ctx.fill()
    ctx.set_source_rgb(0, 0, 0)
    ctx.set_font_size(200)
    ctx.select_font_face("Arial", cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_NORMAL)

    # Generate text extents
    text_extents = []
    for font_size, artist in artist_sizes:
        ctx.set_font_size(font_size)
        text_extents.append(ctx.text_extents(artist))

    rectangles = []
    for i, (font_size, artist) in enumerate(artist_sizes):
        theta = random.randint(0, 300)  # Choose a random start position
        print(artist + "   " + str(font_size))
        extent = text_extents[i]

        good_position = False  # you cannot have a good position until you are
        # colliding with nothing.
        while not good_position:
            # Collision Detection
            ax1, ay2 = get_spiral_coords(theta)  # We get the bottom left
            # corner, so ay2 as y goes down here
            ax2 = ax1 + extent.width
            ay1 = ay2 - extent.height
            # First item will have no rectangles to compare against.
            if i == 0:
                good_position = True
            for j in range(0, len(rectangles)):
                bx1 = rectangles[j][0]
                bx2 = rectangles[j][1]
                by1 = rectangles[j][2]
                by2 = rectangles[j][3]

                x_colliding = ( bx1 <= ax1 and ax1 <= bx2) or (bx1 <= ax2 and ax2 <= bx2) or (ax1 <= bx1 and bx1 <= ax2) or (ax1 <= bx2 and bx2 <= ax2)
                y_colliding = (by1 <= ay1 and ay1 <= by2) or (by1 <= ay2 and ay2 <= by2) or (ay1 <= by1 and by1 <= ay2) or (ay1 <= by2 and by2 <= ay2)

                if x_colliding and y_colliding:
                    good_position = False
                    break
                good_position = True

            # Move a bit
            if not good_position:
                theta += STEPSIZE

        # Draw Text
        x, y = get_spiral_coords(theta)
        ctx.move_to(x, y)
        ctx.set_font_size(font_size)
        r, g, b = choose_colour()
        ctx.set_source_rgb(r, g, b)
        ctx.show_text(artist)
        # Add rectangle to rectangles
        rectangles.append((x, x+extent.width, y-extent.height, y))

    image_data = io.BytesIO()
    surface.write_to_png(image_data)  # Output to PNG
    image = Image.open(image_data)
    callback_success(image)


if __name__ == "__main__":
    root = tk.Tk()
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    app = Application(master=root)
    app.mainloop()

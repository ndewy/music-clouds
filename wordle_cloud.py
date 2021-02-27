import io
import os
import random
import threading
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
from math import ceil, cos, pi, sin

import cairo
import pylast
from PIL import Image, ImageTk

# region LastFM Initialisation
API_KEY = os.environ.get("LASTFM_API_KEY")
API_SECRET = os.environ.get("LASTFM_API_SECRET")

network = pylast.LastFMNetwork(
    api_key=API_KEY,
    api_secret=API_SECRET,
)
# endregion


class ImageWindow(tk.Toplevel):
    """A sub-window to display and save images."""

    def __init__(self, image, master=None):
        super().__init__(master)
        self.topmenu = tk.Menu(self)
        self["menu"] = self.topmenu
        self.filemenu = tk.Menu(self.topmenu, tearoff=0)
        self.topmenu.add_cascade(label="File", menu=self.filemenu)
        self.filemenu.add_command(label="Save As", command=self._save)

        self.resizable(width=False, height=False)
        self.image = image
        thumbnail = image.copy()
        thumbnail.thumbnail((500, 500))
        self.tkimage = ImageTk.PhotoImage(thumbnail)
        self.master = master
        self._create_widgets()

    def _create_widgets(self):
        self.label = tk.Label(self, image=self.tkimage)
        # self.label.bind('<Configure>', self.resize)
        self.label.pack()

    def report_callback_exception(self, *args):
        self.destroy()

    def _handle_resizing(self, event):
        new_width = self.winfo_width()
        new_height = self.winfo_height()
        self.tkimage = ImageTk.PhotoImage(self.image.resize((new_width, new_height)))
        self.label.config(image=self.tkimage)
        self.label.image = self.tkimage

    def _save(self):
        f = filedialog.asksaveasfile(
            mode="wb",
            parent=self,
            title="Save Picture",
            filetypes=[("PNG", "*.png")],
            defaultextension=".png",
        )

        self.image.save(f, format="png")
        f.close()


class Application(tk.Frame):
    """ Main Application class"""

    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.master.title("LastFM")
        self.pack()
        self._create_widgets()

        self.master.resizable(width=False, height=False)

    def _create_widgets(self):
        self.options = {}

        self.options["time"] = tk.StringVar()
        time_label = tk.Label(self, text="Time period:")
        time_menu = tk.OptionMenu(self, self.options["time"], *TIME_PERIODS.keys())
        self.options["time"].set("All Time")

        self.options["type"] = tk.StringVar()
        type_label = tk.Label(self, text="Select Graph type:")
        type_menu = tk.OptionMenu(self, self.options["type"], *ITEM_FUNCTIONS.keys())
        self.options["type"].set("Artist")

        self.options["limit"] = tk.StringVar()
        self.validate = self.master.register(self._is_number)
        limit_input = tk.Entry(
            self,
            textvariable=self.options["limit"],
            validatecommand=(self.validate, "%S"),
            validate="key",
        )
        limit_input.insert(0, "20")
        limit_label = tk.Label(self, text="Limit:")

        self.options["user"] = tk.StringVar()
        users_label = tk.Label(self, text="Username:")
        self.options["user"].set("ndewy")
        users_input = tk.Entry(self, textvariable=self.options["user"])

        create = tk.Button(self)
        create["text"] = "Create"
        create["command"] = self._on_create

        time_label.grid(column=0, row=0)
        time_menu.grid(column=1, row=0)
        type_label.grid(column=0, row=1)
        type_menu.grid(column=1, row=1)
        limit_label.grid(column=0, row=2)
        limit_input.grid(column=1, row=2)
        users_label.grid(column=0, row=3)
        users_input.grid(column=1, row=3)
        create.grid(column=2, row=4)

    def _on_create(self):
        period = TIME_PERIODS[self.options["time"].get()]
        user = self.options["user"].get()
        item_func = ITEM_FUNCTIONS[self.options["type"].get()]

        if self.options["limit"].get() == "":
            limit = 10
        else:
            limit = int(self.options["limit"].get())
        t = threading.Thread(
            target=self._generate,
            args=(item_func, limit, period, user),
        )
        t.start()

    def _generate(self, item_func, limit, period, user):
        """Threaded wrapper function to generate_cloud().

        Intended to be run in a background thread.
        Wraps the generate_cloud() function with callbacks and LastFM fetching.
        """
        try:
            items = item_func(user, period, limit)
        except pylast.WSError as e:
            self._on_generation_fail(e)
            return

        image = generate_cloud(items)
        self._on_generation_success(image)

    def _on_generation_success(self, image):
        ImageWindow(image, master=self)

    def _on_generation_fail(self, msg):
        messagebox.showerror("Generation Failed", str(msg))

    def _is_number(self, char):
        return char.isdigit()


def _get_spiral_coords(theta):
    x = ceil(CURVE_MULTIPLIER * theta * cos(theta)) + WIDTH / 2
    y = ceil(CURVE_MULTIPLIER * theta * sin(theta)) + HEIGHT / 2
    return x, y


def _choose_colour():
    # All colours must be atleast 0.5 to stop looking too dark
    while True:
        r = random.uniform(0.4, 1)
        g = random.uniform(0.4, 1)
        b = random.uniform(0.4, 1)
        # However, we dont want to be pure white, or near to it, so we max the
        # sum to 2 (out of a maximum of 3).
        if (r + g + b) < 2:
            break
    return r, g, b


def _get_albums(user, period, limit):
    """ Returns parsed list of album names """

    albums_raw = network.get_user(user).get_top_albums(period=period, limit=limit)
    albums = [album.item.get_title() for album in albums_raw]
    return albums


def _get_artists(user, period, limit):
    """ Returns parsed list of artist names """

    artists_raw = network.get_user(user).get_top_artists(period=period, limit=limit)
    artists = [artist.item.get_name() for artist in artists_raw]
    return artists


def _get_tracks(user, period, limit):

    tracks_raw = network.get_user(user).get_top_tracks(period=period, limit=limit)
    tracks = [track.item.get_name() for track in tracks_raw]
    return tracks


# region Parameters
WIDTH, HEIGHT = 2000, 1000
MAX_FONT_SIZE = 150
MIN_FONT_SIZE = 30
BASE = 1.1
STEPSIZE = pi / 200
CURVE_MULTIPLIER = 1

# endregion


def generate_cloud(items):
    """Generates a word cloud.

    Generates a word cloud populated with the words fed in.

    Args:
        items: The words to populate the cloud with.

    Returns:
        An byte-like object containing a PNG image of the word cloud.
    """

    # Make font sizes follow negative exponential curve with base BASE
    font_sizes = []
    for i, item in enumerate(items):
        size = ceil(MAX_FONT_SIZE / (BASE ** i))
        if size <= MIN_FONT_SIZE:
            size = MIN_FONT_SIZE
        font_sizes.append((item, size))

    # region Cairo Image processing
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)
    ctx = cairo.Context(surface)
    ctx.rectangle(0, 0, WIDTH, HEIGHT)
    ctx.set_source_rgb(1, 1, 1)
    ctx.fill()
    ctx.set_source_rgb(0, 0, 0)
    ctx.set_font_size(200)
    ctx.select_font_face("Arial", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)

    # Generate text extents
    text_extents = []
    for item, font_size in font_sizes:
        ctx.set_font_size(font_size)
        text_extents.append(ctx.text_extents(item))

    # Combine words, font sizes, and extents into single object (so we can shuffle it later on)
    words = [
        (font_sizes[i][0], font_sizes[i][1], text_extents[i])
        for i in range(len(font_sizes))
    ]
    # Shuffle words to make placement of big words vs small words more random
    # but, always place largest word in the centre
    words = [words[0], *random.sample(words[1:], k=len(words) - 1)]
    random.shuffle(words)

    rectangles = []
    for (item, font_size, extent) in words:
        theta = random.randint(0, 300)  # Choose a random start position
        print(item + "   " + str(font_size))

        good_position = False  # you cannot have a good position until you are
        # colliding with nothing.
        while not good_position:  # Collision Detection

            # Generate rectangle that we are trying to place
            # Let top left of the text sit on the spiral
            ax1, ay1 = _get_spiral_coords(theta)
            # Make ax1,ay1 start from the bounding box, not the reference point
            ax1 += extent.x_bearing
            ay1 += extent.y_bearing
            # The width and height represent the bounding box
            ax2 = ax1 + extent.width
            ay2 = ay1 + extent.height

            if (
                len(rectangles) == 0
            ):  # First item will have no rectangles to compare against.
                good_position = True
            for j in range(0, len(rectangles)):
                bx1 = rectangles[j][0]
                bx2 = rectangles[j][1]
                by1 = rectangles[j][2]
                by2 = rectangles[j][3]

                x_colliding = (
                    (bx1 <= ax1 and ax1 <= bx2)
                    or (bx1 <= ax2 and ax2 <= bx2)
                    or (ax1 <= bx1 and bx1 <= ax2)
                    or (ax1 <= bx2 and bx2 <= ax2)
                )
                y_colliding = (
                    (by1 <= ay1 and ay1 <= by2)
                    or (by1 <= ay2 and ay2 <= by2)
                    or (ay1 <= by1 and by1 <= ay2)
                    or (ay1 <= by2 and by2 <= ay2)
                )

                if x_colliding and y_colliding:
                    good_position = False
                    break
                good_position = True

            # Move a bit
            if not good_position:
                theta += STEPSIZE

        # Turn correct bounding box coordinates into reference point coordinates in order to draw the text
        x = ax1 - extent.x_bearing
        y = ay1 - extent.y_bearing

        # Draw text
        ctx.move_to(x, y)
        ctx.set_font_size(font_size)
        r, g, b = _choose_colour()
        ctx.set_source_rgb(r, g, b)
        ctx.show_text(item)

        # Draw text extent (debug)
        # ctx.rectangle(ax1, ay1, extent.width, extent.height)
        # ctx.stroke()

        # Add rectangle to list of drawn rectangles
        rectangles.append((ax1, ax2, ay1, ay2))

    image_data = io.BytesIO()
    surface.write_to_png(image_data)  # Output to PNG
    image = Image.open(image_data)
    return image


# region LOOKUP TABLES
TIME_PERIODS = {
    "All Time": pylast.PERIOD_OVERALL,
    "Last Week": pylast.PERIOD_7DAYS,
    "Last Month": pylast.PERIOD_1MONTH,
    "Last 3 Months": pylast.PERIOD_3MONTHS,
    "Last 6 months": pylast.PERIOD_6MONTHS,
    "Last Year": pylast.PERIOD_12MONTHS,
}

# Functions used to populate words variables, depending on choice in the UI.
ITEM_FUNCTIONS = {"Artist": _get_artists, "Album": _get_albums, "Song": _get_tracks}

# endregion

if __name__ == "__main__":
    root = tk.Tk()
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    app = Application(master=root)
    app.mainloop()

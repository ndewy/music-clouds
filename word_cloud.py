import io
import os
import random
import threading
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
from math import ceil, cos, exp, floor, pi, sin

import cairo
import pylast
from colorutils import Color
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

        self.options["font"] = tk.StringVar()
        font_label = tk.Label(self, text="Font:")
        self.options["font"].set("Impact")
        font_input = tk.Entry(self, textvariable=self.options["font"])

        self.options["all_caps"] = tk.BooleanVar()
        self.options["bold"] = tk.BooleanVar()
        allcaps_checkbox = tk.Checkbutton(
            self, text="Capitalised", variable=self.options["all_caps"]
        )
        bold_checkbox = tk.Checkbutton(self, text="Bold", variable=self.options["bold"])

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
        font_label.grid(column=0, row=3)
        font_input.grid(column=1, row=3)
        allcaps_checkbox.grid(column=0, row=4, sticky="W")
        bold_checkbox.grid(column=0, row=5, sticky="W")
        users_label.grid(column=0, row=6)
        users_input.grid(column=1, row=6)
        create.grid(column=2, row=7)

    def _on_create(self):
        period = TIME_PERIODS[self.options["time"].get()]
        user = self.options["user"].get()
        item_func = ITEM_FUNCTIONS[self.options["type"].get()]
        font = self.options["font"].get()
        all_caps = self.options["all_caps"].get()
        bold = self.options["bold"].get()
        5
        if self.options["limit"].get() == "":
            limit = 10
        else:
            limit = int(self.options["limit"].get())
        t = threading.Thread(
            target=self._generate,
            args=(item_func, limit, period, user, font, all_caps, bold),
        )
        t.start()

    def _generate(self, item_func, limit, period, user, font, all_caps, bold):
        """Threaded wrapper function to generate_cloud().

        Intended to be run in a background thread.
        Wraps the generate_cloud() function with callbacks and LastFM fetching.
        """
        # Half life proportion calculated from original base 1.1 with n = 20
        half_life = 0.25 * limit  # Halves every 37%.
        try:
            items = item_func(user, period, limit)
        except pylast.WSError as e:
            self._on_generation_fail(e)
            return
        image = generate_cloud(
            items, half_life, 150, 30, font, all_caps=all_caps, bold=bold
        )
        self._on_generation_success(image)

    def _on_generation_success(self, image):
        ImageWindow(image, master=self)

    def _on_generation_fail(self, msg):
        messagebox.showerror("Generation Failed", str(msg))

    def _is_number(self, char):
        return char.isdigit()


def _get_spiral_coords(theta):
    x = ceil(CURVE_MULTIPLIER * theta * cos(theta)) + 8000 / 2
    y = ceil(CURVE_MULTIPLIER * theta * sin(theta)) + 8000 / 2
    return x, y


def _generate_exponential_decay(n, half_life, maximum, minimum):
    # Calculate decay constant from half_life
    decay_constant = 0.69314718 / half_life
    decay = lambda x: (maximum - minimum) * exp(-decay_constant * x) + minimum
    return [decay(i) for i in range(n)]


def _generate_colours(n, half_life):
    # Cycle through hues linearly
    min_hue = 0  # Hue goes 0 -> 360 then loops around
    # the loop around is implemented later
    max_hue = 940
    hue_step = (max_hue - min_hue) / n

    # Decrease saturation exponentially
    max_saturation = 0.6  # Saturation goes 0 -> 1
    min_saturation = 0
    saturation_values = _generate_exponential_decay(n,half_life,max_saturation,min_saturation)

    brightness = 0.6  # Brigtness goes 0 (dark) -> 1 (light)

    colours = []  # Array of rgb tuples
    current_hue = max_hue
    for i in range(n):
        current_hue = (current_hue + hue_step) % 360
        # Saturation decays exponentially from max_sat -> min_sat
        # This is shown interatively in geogebra file saturation_decay.gbb
        colour = Color(hsv=(current_hue, saturation_values[i], brightness)).rgb
        colours.append(colour)
    return colours


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
BASE = 1.1
STEPSIZE = pi / 400
CURVE_MULTIPLIER = 0.6
PAD_X = 5
PAD_Y = 5

# endregion


def generate_cloud(
    items,
    half_life,
    max_font_size,
    min_font_size,
    font="Impact",
    all_caps=False,
    bold=False,
):
    """Generates a word cloud.

    Generates a word cloud populated with the words specified.

    Args:
        items: The words to populate the cloud with.
        half_life: The amount of items it takes for the font size to half.
        max_font_size: The maximum font size.
        min_font_size: The minimum font size
        font: default: Impact. The font to use. If the font given is invalid, this defaults to Arial.
        all_caps: default: True. A boolean representing whether each word should be fully UPPER CASE or Standard Case.
        bold: default: False. A boolean representing whether a font should be in bold.

    Returns:
        An byte-like object containing a PNG image of the word cloud.
    """
    # Capitalise items.
    if all_caps:
        items = [item.upper() for item in items]

    # Make font sizes follow negative exponential curve.
    # Calculate decay constant from half_life
    sizes = _generate_exponential_decay(
        len(items), half_life, max_font_size, min_font_size
    )
    font_sizes = [(items[i], sizes[i]) for i in range(len(items))]

    # region Cairo Image processing
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 8000, 8000)
    ctx = cairo.Context(surface)
    # ctx.rectangle(0, 0, 8000, 8000)
    # ctx.set_source_rgb(1, 1, 1)
    # ctx.fill()
    # ctx.set_source_rgb(0, 0, 0)
    # ctx.set_font_size(200)
    font_weight = cairo.FONT_WEIGHT_NORMAL
    if bold:
        font_weight = cairo.FONT_WEIGHT_BOLD
    ctx.select_font_face(font, cairo.FONT_SLANT_NORMAL, font_weight)

    # Generate text extents
    text_extents = []
    for item, font_size in font_sizes:
        ctx.set_font_size(font_size)
        text_extents.append(ctx.text_extents(item))

    # Generate colours
    colours = _generate_colours(len(items), 0.25*len(items))
    # Combine words, font sizes, extents, and colours into single object (so we can shuffle it later on)
    words = [
        (font_sizes[i][0], font_sizes[i][1], text_extents[i], colours[i])
        for i in range(len(items))
    ]
    # Shuffle words to make placement of big words vs small words more random
    # but, always place largest word in the centre
    words = [words[0], *random.sample(words[1:], k=len(words) - 1)]
    random.shuffle(words)

    rectangles = []
    for (item, font_size, extent, colour) in words:
        theta = random.randint(
            0, 300 * (len(items) / 20)
        )  # Choose a random start position
        print(item + "   " + str(font_size))

        good_position = False  # you cannot have a good position until you are
        # colliding with nothing.
        while not good_position:  # Collision Detection

            # Generate rectangle that we are trying to place
            # Let top left of the text sit on the spiral
            ax1, ay1 = _get_spiral_coords(theta)
            # Make ax1,ay1 start from the bounding box, not the reference point
            ax1 += extent.x_bearing - PAD_X
            ay1 += extent.y_bearing - PAD_Y
            # The width and height represent the bounding box
            ax2 = ax1 + extent.width + PAD_X
            ay2 = ay1 + extent.height + PAD_Y

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
        x = ax1 - extent.x_bearing + PAD_X
        y = ay1 - extent.y_bearing + PAD_Y

        # Draw text
        ctx.move_to(x, y)
        ctx.set_font_size(font_size)
        r, g, b = colour
        ctx.set_source_rgb(r / 255, g / 255, b / 255)
        ctx.show_text(item)

        # Draw text extent (debug)
        # ctx.rectangle(ax1, ay1, extent.width, extent.height)
        # ctx.stroke()

        # Add rectangle to list of drawn rectangles
        rectangles.append((ax1, ax2, ay1, ay2))

    image_data = io.BytesIO()
    surface.write_to_png(image_data)  # Output to PNG
    image = Image.open(image_data)
    image_cropped = image.crop(image.getbbox())
    return image_cropped


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

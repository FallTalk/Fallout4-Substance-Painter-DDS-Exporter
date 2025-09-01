__author__ = "Emil Eldstål, PraedythXIV, Bryant21"
__copyright__ = "Original Copyright 2023, Emil Eldstål"
__original_version__ = "0.1.1"
__praedyth_version__ = "0.1.5"
__forkedVersion__ = "1.1.0"
__painterVersion__ = "11.0.0"

import logging
from pathlib import Path

# Qt5 vs Qt6 check import
import substance_painter as sp

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtCore import Qt, QEvent, Signal, QObject
    from PySide6.QtGui import QKeyEvent

    QtVersion = 6
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from PySide2.QtCore import Qt, QEvent, Signal, QObject
    from PySide2.QtGui import QKeyEvent

    QtVersion = 5

import substance_painter.ui
import substance_painter.event
import substance_painter.logging as log

import os
import configparser
import subprocess
import shutil
import numpy as np
from PIL import Image
from functools import partial
import traceback

# Remove the basicConfig call to prevent default handlers
logger = logging.getLogger(__name__)

# Define the default TexConv path
DEFAULT_TEXCONV_PATH = "C:\\DirectXTex\\Texconv\\texconv.exe"

"""
Apply Photoshop-style levels adjustment to an image using Pillow.

Parameters:
-----------
image_path : str
    Path to the input image
red_levels : tuple
    Red channel levels (input_black, gamma, input_white)
green_levels : tuple
    Green channel levels (input_black, gamma, input_white)
blue_levels : tuple
    Blue channel levels (input_black, gamma, input_white)
output_path : str, optional
    Path to save the adjusted image. If None, saves as 'adjusted_' + original filename

Returns:
--------
PIL.Image.Image
    The adjusted image as a PIL Image object
"""


def apply_levels_to_channel(channel_array, input_black, gamma, input_white):
    """Apply levels adjustment to a single channel array"""
    # Normalize input black and white points to 0-1 range
    input_black = input_black / 255.0
    input_white = input_white / 255.0

    # Convert channel to float for processing
    channel_float = channel_array.astype(np.float32) / 255.0

    # Clip values to input range
    channel_float = np.clip((channel_float - input_black) / (input_white - input_black), 0, 1)

    # Apply gamma correction
    if gamma != 1.0:
        channel_float = np.power(channel_float, 1.0 / gamma)

    # Convert back to 0-255 range
    adjusted_channel = (channel_float * 255).astype(np.uint8)

    return adjusted_channel


def fallout_4_adjustments(image_path,
                          red_levels=(30, 1.0, 145),
                          green_levels=(0, 0.5, 255),
                          blue_levels=(0, 1.0, 255),
                          output_path=None):
    # Open the image with Pillow
    try:
        image = Image.open(image_path)
        # Convert to RGB if it's not already (handles RGBA, grayscale, etc.)
        if image.mode != 'RGB':
            image = image.convert('RGB')
    except Exception as e:
        raise ValueError(f"Could not load image from {image_path}: {e}")

    # Convert to numpy array for processing
    img_array = np.array(image)

    # Split into RGB channels
    r_channel = img_array[:, :, 0]
    g_channel = img_array[:, :, 1]
    b_channel = img_array[:, :, 2]

    # Apply levels adjustment to each channel
    r_adjusted = apply_levels_to_channel(r_channel, *red_levels)
    g_adjusted = apply_levels_to_channel(g_channel, *green_levels)
    b_adjusted = apply_levels_to_channel(b_channel, *blue_levels)

    # Reconstruct the image array
    adjusted_array = np.stack([r_adjusted, g_adjusted, b_adjusted], axis=2)

    # Convert back to PIL Image
    adjusted_image = Image.fromarray(adjusted_array)

    # Generate output path if not provided
    if output_path is None:
        input_path = Path(image_path)
        output_path = input_path.parent / f"{input_path.name}"

    # Save the adjusted image
    adjusted_image.save(output_path)
    print(f"Adjusted image saved to: {output_path}")

    return adjusted_image


# Function to choose the TexConv executable
def choose_texconv_executable():
    main_window = substance_painter.ui.get_main_window()
    path = QtWidgets.QFileDialog.getExistingDirectory(
        main_window, "Choose Texconv directory")
    if path:
        texconv_exe = os.path.join(path, "texconv.exe")
        if os.path.exists(texconv_exe):
            return texconv_exe  # Ensure correct path formatting
        else:
            QtWidgets.QMessageBox.warning(main_window, "Invalid Path",
                                          "texconv.exe not found in the selected directory.")
            return ""
    else:
        return ""  # Return empty string if no directory is selected


# Config class to hold all configuration parameters
class Config:
    def __init__(self):
        # Default values
        self.texconv_path = DEFAULT_TEXCONV_PATH
        self.export_dds = False
        self.overwrite_dds = False
        self.adjust_red = False
        self.red_max = 145
        self.red_min = 30
        self.red_gamma = 1.0
        self.green_black = 0
        self.green_gamma = 0.5
        self.green_white = 255
        self.output_dir = ''
        self.show_suffixes = True
        self.show_levels = True
        self.show_log = True
        self.show_wiki = False
        self.suffix_format_map = {}

# Function to load and update settings from the ini configuration file
def config_ini(prompt_texconv_path, profile_name=None):
    # Get the path to the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Define the path to the Universal-DDS-Exporter-PluginSettings.ini file
    ini_file_path = os.path.join(script_dir, "Universal-DDS-Exporter-PluginSettings.ini")

    # Create a ConfigParser object
    config = configparser.ConfigParser()
    config.optionxform = str  # Preserve case of options

    # Create a Config object to return
    config_obj = Config()

    # If INI file doesn't exist, create it with default [General] section
    if not os.path.exists(ini_file_path):
        config['General'] = {
            'TexConvDirectory': DEFAULT_TEXCONV_PATH,
            'ExportDDSFiles': 'False',
            'OverwriteDDSFiles': 'False',
            'AdjustSpecularRed': 'False',
            'RedMinValue': '30',
            'RedMaxValue': '145',
            'RedGamma': '1.0',
            'GreenBlack': '0',
            'GreenGamma': '0.5',
            'GreenWhite': '255',
            'OutputDir': '',
            'ShowSuffixes': 'True',
            'ShowLevels': 'True',
            'ShowLog': 'True',
            'ShowWiki': 'False'
        }
        with open(ini_file_path, 'w') as configfile:
            config.write(configfile)

    # Read the INI file with error handling
    try:
        config.read(ini_file_path)
    except configparser.ParsingError as e:
        logger.error(f"INI parsing error: {e}")
        QtWidgets.QMessageBox.critical(None, "Configuration Error",
                                       "The configuration file is corrupted and will be reset to default settings.")
        # Reset to default settings
        config = configparser.ConfigParser()
        config.optionxform = str
        config['General'] = {
            'TexConvDirectory': DEFAULT_TEXCONV_PATH,
            'ExportDDSFiles': 'False',
            'OverwriteDDSFiles': 'False',
            'AdjustSpecularRed': 'False',
            'RedMaxValue': '185',
            'RedGamma': '1.0',
            'GreenBlack': '0',
            'GreenGamma': '0.5',
            'GreenWhite': '255',
            'OutputDir': '',
            'ShowSuffixes': 'True',
            'ShowLevels': 'True',
            'ShowLog': 'True',
            'ShowWiki': 'False'
        }
        with open(ini_file_path, 'w') as configfile:
            config.write(configfile)
        profile_name = None  # Reset profile if necessary

    # Ensure [General] section exists
    if 'General' not in config:
        config['General'] = {
            'TexConvDirectory': DEFAULT_TEXCONV_PATH,
            'ExportDDSFiles': 'False',
            'OverwriteDDSFiles': 'False',
            'AdjustSpecularRed': 'False',
            'RedMinValue': '30',
            'RedMaxValue': '145',
            'RedGamma': '1.0',
            'GreenBlack': '0',
            'GreenGamma': '0.5',
            'GreenWhite': '255',
            'OutputDir': '',
            'ShowSuffixes': 'True',
            'ShowLevels': 'True',
            'ShowLog': 'True',
            'ShowWiki': 'False'
        }

    # Update TexConv path if prompt_texconv_path is True
    if prompt_texconv_path:
        new_texconv_path = choose_texconv_executable()
        if new_texconv_path:
            config['General']['TexConvDirectory'] = new_texconv_path
        else:
            # If user cancels the dialog, retain the existing path
            pass

    # Assign settings to Config object
    config_obj.texconv_path = config['General'].get('TexConvDirectory', DEFAULT_TEXCONV_PATH)
    config_obj.export_dds = config.getboolean('General', 'ExportDDSFiles', fallback=False)
    config_obj.overwrite_dds = config.getboolean('General', 'OverwriteDDSFiles', fallback=False)
    config_obj.adjust_red = config.getboolean('General', 'AdjustSpecularRed', fallback=False)
    config_obj.red_max = config.getint('General', 'RedMaxValue', fallback=145)
    config_obj.red_min = config.getint('General', 'RedMinValue', fallback=30)
    config_obj.red_gamma = config.getfloat('General', 'RedGamma', fallback=1.0)
    config_obj.green_black = config.getint('General', 'GreenBlack', fallback=0)
    config_obj.green_gamma = config.getfloat('General', 'GreenGamma', fallback=0.5)
    config_obj.green_white = config.getint('General', 'GreenWhite', fallback=255)
    config_obj.output_dir = config['General'].get('OutputDir', '')
    config_obj.show_suffixes = config.getboolean('General', 'ShowSuffixes', fallback=True)
    config_obj.show_levels = config.getboolean('General', 'ShowLevels', fallback=True)
    config_obj.show_log = config.getboolean('General', 'ShowLog', fallback=True)
    config_obj.show_wiki = config.getboolean('General', 'ShowWiki', fallback=False)

    # Handle profiles if profile_name is provided
    config_obj.suffix_format_map = {}
    if profile_name:
        suffix_section = f"{profile_name}_SuffixFormats"
        if suffix_section in config:
            items = config.items(suffix_section)
            # Detect duplicates
            seen = set()
            for key, value in items:
                if key in seen:
                    log.warning(f"Duplicate suffix '{key}' found in configuration. Ignoring subsequent entries.")
                    continue  # Skip duplicates
                seen.add(key)
                config_obj.suffix_format_map[key] = value
        else:
            # Create the profile section if it doesn't exist
            config[suffix_section] = {}
            with open(ini_file_path, 'w') as configfile:
                config.write(configfile)

    return config_obj


# Function to convert PNG files to DDS format using TexConv
def convert_png_to_dds(config, sourcePNG, suffix_format_map=None):
    """
    Convert PNG or TGA files to DDS format using TexConv
    
    Parameters:
    -----------
    config : Config
        Configuration object containing all settings
    sourcePNG : str
        Path to the source PNG or TGA file
    suffix_format_map : dict, optional
        Map of suffix to format options. If None, uses config.suffix_format_map
    """
    # Use passed suffix_format_map or config's map
    suffix_map = suffix_format_map if suffix_format_map is not None else config.suffix_format_map
    
    if not config.texconv_path or not os.path.exists(config.texconv_path):
        log.error("Invalid TexConv path.")
        return "Invalid TexConv path."

    sourceFolder = os.path.dirname(sourcePNG)

    # Use custom output directory if specified, otherwise use source directory
    outputFolder = os.path.normpath(config.output_dir) if config.output_dir else os.path.join(sourceFolder, "DDS")
    outputFile = os.path.join(outputFolder, os.path.splitext(os.path.basename(sourcePNG))[0] + ".dds")

    # Ensure DDS subfolder exists
    if not os.path.exists(outputFolder):
        os.makedirs(outputFolder)
        log.info(f"Created output directory: {outputFolder}")

    filename = os.path.basename(sourcePNG)
    if filename.endswith(".png") or filename.endswith(".tga"):
        sourceFile = os.path.splitext(filename)[0]

        # Check if we should adjust red channel (either _s files or all files if enabled)
        if config.adjust_red and (filename.lower().endswith("_s.png") or filename.lower().endswith("_s.tga")):
            log.info(
                f"Applying Fallout 4 adjustments for {filename} (Red clamp {config.red_min}-{config.red_max}, Red gamma {config.red_gamma}, Green levels {config.green_black}-{config.green_white}, gamma {config.green_gamma})")
            try:
                # Create backup of original file
                original_path = os.path.join(sourceFolder,
                                             f"{os.path.splitext(filename)[0]}_original{os.path.splitext(filename)[1]}")
                shutil.copy2(sourcePNG, original_path)
                log.info(f"Saved original file as: {original_path}")

                # Load, adjust, and overwrite original file
                # Use full Levels for each channel; keep blue as identity
                fallout_4_adjustments(
                    sourcePNG,
                    red_levels=(config.red_min, config.red_gamma, config.red_max),
                    green_levels=(config.green_black, config.green_gamma, config.green_white),
                    blue_levels=(0, 1.0, 255),
                    output_path=sourcePNG
                )
            except Exception as e:
                log.error(f"Failed to adjust red channel for {filename}: {e}")
                return f"Failed to adjust red channel for {filename}"

        # Extract suffix and choose corresponding DDS format from suffix_format_map
        if '_' in sourceFile:
            suffix = sourceFile.rsplit('_', 1)[-1].rstrip('_')
            if not suffix:
                QtWidgets.QMessageBox.warning(None, "Invalid Suffix",
                                              f"No valid suffix found in '{filename}'. Using default format.")
                format_option = "BC7_UNORM"
            else:
                format_option = (
                    suffix_map.get(suffix.lower())
                    if suffix_map.get(suffix.lower()) is not None
                    else suffix_map.get(suffix.upper(), "BC7_UNORM")
                )
        else:
            # If no suffix defined
            suffix = None
            format_option = "BC7_UNORM"

        log.info(f"Processing {filename}")
        log.info(f"Extracted suffix: {suffix}")
        log.info(f"Chosen format: {format_option}")

        # Set overwrite_option based on the state
        overwrite_option = ["-y"] if config.overwrite_dds else []

        # Check if DDS file already exists and if overwrite is disabled
        if config.overwrite_dds or not os.path.exists(outputFile):
            texconv_cmd = [
                              config.texconv_path,
                              "-nologo",
                          ] + overwrite_option + [
                              "-o", outputFolder,
                              "-f", format_option,
                              os.path.join(sourceFolder, filename)
                          ]

            log.info(f"Running command: {' '.join(texconv_cmd)}")

            # Run TexConv command in the background without showing a command window
            try:
                # CREATE_NO_WINDOW flag (0x08000000) prevents command window from appearing
                subprocess.Popen(texconv_cmd, shell=False, 
                               creationflags=0x08000000, 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE)
                log.info(f"Started conversion of {filename} to {outputFile} using {format_option}")
                return f"Started conversion of {filename} to {outputFile} with format {format_option}"
            except Exception as e:
                log.error(f"Failed to convert {filename}: {e}")
                return f"Failed to convert {filename}"
        else:
            log.info(f"Skipping conversion for {filename}, DDS file already exists and overwrite is disabled.")
            return f"Skipping conversion for {filename}, DDS file already exists."

    return ""


# Custom Qt Logging Handler
class QtLogHandler(QObject, logging.Handler):
    log_message = Signal(str)  # Renamed signal to avoid conflicts

    def __init__(self):
        super().__init__()
        logging.Handler.__init__(self)  # Explicitly initialize logging.Handler
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    def emit(self, record, excinfo=None):
        try:
            msg = self.format(record)
            self.log_message.emit(msg)
        except Exception as e:
            log.error(f"Logging emit error: {e}")


# Main plugin class
class UniversalDDSPlugin(QObject):
    # Define a signal for updating the log
    log_signal = Signal(str)

    def __init__(self):
        super().__init__()
        # Flag to indicate UI is being updated
        self.updating_ui = False
        # Flag to prevent multiple cleanups
        self.is_cleaned_up = False

        # Initialize global settings without prompting for TexConv path
        self.config = config_ini(prompt_texconv_path=False)
        self.version = __forkedVersion__

        # Create log area
        self.log = QtWidgets.QTextEdit()
        self.log.setReadOnly(True)

        # Main window and layout initialization
        self.window = QtWidgets.QWidget()

        main_layout = QtWidgets.QVBoxLayout()
        top_row_layout = QtWidgets.QHBoxLayout()

        # Profile management UI
        profile_layout = QtWidgets.QHBoxLayout()
        self.profile_dropdown = QtWidgets.QComboBox()
        self.profile_dropdown.setToolTip("Select Profile")
        self.button_add_profile = QtWidgets.QPushButton("Add Profile")
        self.button_delete_profile = QtWidgets.QPushButton("Delete Profile")
        profile_layout.addWidget(QtWidgets.QLabel("Profile:"))
        profile_layout.addWidget(self.profile_dropdown)
        profile_layout.addWidget(self.button_add_profile)
        profile_layout.addWidget(self.button_delete_profile)

        # Initialize suffix_format_layout before calling load_suffix_formats
        suffix_format_scroll_area = QtWidgets.QScrollArea()
        suffix_format_widget = QtWidgets.QWidget()
        self.suffix_format_layout = QtWidgets.QVBoxLayout(suffix_format_widget)
        suffix_format_scroll_area.setWidget(suffix_format_widget)
        suffix_format_scroll_area.setWidgetResizable(True)
        suffix_format_scroll_area.setMinimumWidth(100)

        # Buttons
        self.checkbox = QtWidgets.QCheckBox("Export DDS files")
        self.checkbox.setChecked(self.config.export_dds)
        self.checkbox_overwrite = QtWidgets.QCheckBox("Overwrite DDS files")
        self.checkbox_overwrite.setChecked(self.config.overwrite_dds)
        # Create Fallout 4 Adjustments checkbox
        self.checkbox_adjust_red = QtWidgets.QCheckBox("Fallout 4 Adjustments")
        self.checkbox_adjust_red.setToolTip("Apply Red clamp and Green levels (Photoshop Levels)")
        self.checkbox_adjust_red.setChecked(self.config.adjust_red)
        self.button_texconv = QtWidgets.QPushButton("Texconv location")
        self.button_clear = QtWidgets.QPushButton("Clear Log")
        self.button_display_log = QtWidgets.QPushButton("Hide Log")
        self.button_show_wiki = QtWidgets.QPushButton("Wiki")
        self.button_export_textures = QtWidgets.QPushButton(">> Export Textures <<")
        self.button_toggle_suffix = QtWidgets.QPushButton("Hide Suffixes")
        self.button_toggle_levels = QtWidgets.QPushButton("Hide Levels")

        # Version label
        version_label = QtWidgets.QLabel(f"Version: {self.version}")

        # Buttons to add or remove suffix formats
        self.button_add = QtWidgets.QPushButton("Add")
        self.button_remove = QtWidgets.QPushButton("Remove")

        # Group all checkboxes together in their own section
        checkbox_group = QtWidgets.QGroupBox("Options")
        checkbox_layout = QtWidgets.QVBoxLayout()
        checkbox_layout.addWidget(self.checkbox)
        checkbox_layout.addWidget(self.checkbox_overwrite)
        checkbox_layout.addWidget(self.checkbox_adjust_red)  # Move this checkbox from red_adjust_layout to here
        checkbox_group.setLayout(checkbox_layout)

        # Make buttons responsive by organizing them in a flow layout (using QGridLayout)
        buttons_widget = QtWidgets.QWidget()
        buttons_layout = QtWidgets.QGridLayout(buttons_widget)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(6)

        # Add buttons in a grid - they will flow to next row when window is resized
        buttons_layout.addWidget(self.button_export_textures, 0, 0)
        buttons_layout.addWidget(self.button_texconv, 0, 1)
        buttons_layout.addWidget(self.button_clear, 0, 2)
        buttons_layout.addWidget(self.button_display_log, 1, 0)
        buttons_layout.addWidget(self.button_show_wiki, 1, 1)
        buttons_layout.addWidget(self.button_toggle_suffix, 1, 2)
        buttons_layout.addWidget(self.button_toggle_levels, 2, 0)
        buttons_layout.addWidget(version_label, 3, 0, 1, 3)  # Span across 3 columns

        # Add checkbox group and buttons to top row
        top_row_layout.addWidget(checkbox_group)
        top_row_layout.addWidget(buttons_widget)

        # Second row - Output Directory and Red Adjustment controls
        second_row_layout = QtWidgets.QHBoxLayout()

        # Output Directory controls
        output_dir_layout = QtWidgets.QHBoxLayout()
        self.output_dir_label = QtWidgets.QLabel("Output Directory:")
        self.output_dir_edit = QtWidgets.QLineEdit()
        self.output_dir_edit.setPlaceholderText("Leave empty for same directory as source")
        self.output_dir_edit.setText(self.config.output_dir)
        self.button_browse_dir = QtWidgets.QPushButton("Browse...")

        output_dir_layout.addWidget(self.output_dir_label)
        output_dir_layout.addWidget(self.output_dir_edit)
        output_dir_layout.addWidget(self.button_browse_dir)

        # Create adjustments controls (without the checkbox which is now in checkbox_group)
        # Add min/max value controls for Red
        self.red_min_label = QtWidgets.QLabel("Red Min:")
        self.red_min_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.red_min_slider.setRange(0, 254)
        self.red_min_slider.setValue(self.config.red_min)
        self.red_min_value = QtWidgets.QLabel(str(self.config.red_min))

        self.red_max_label = QtWidgets.QLabel("Red Max:")
        self.red_max_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.red_max_slider.setRange(1, 255)
        self.red_max_slider.setValue(self.config.red_max)
        self.red_max_value = QtWidgets.QLabel(str(self.config.red_max))

        # Red gamma slider (0.10 to 3.00 mapped via integer slider 10-300)
        self.red_gamma_label = QtWidgets.QLabel("Red Gamma:")
        self.red_gamma_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.red_gamma_slider.setRange(10, 300)
        self.red_gamma_slider.setValue(int(round(self.config.red_gamma * 100)))
        self.red_gamma_value = QtWidgets.QLabel(f"{self.config.red_gamma:.2f}")

        # Green levels sliders
        self.green_black_label = QtWidgets.QLabel("Green Black:")
        self.green_black_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.green_black_slider.setRange(0, 254)
        self.green_black_slider.setValue(self.config.green_black)
        self.green_black_value = QtWidgets.QLabel(str(self.config.green_black))

        self.green_white_label = QtWidgets.QLabel("Green White:")
        self.green_white_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.green_white_slider.setRange(1, 255)
        self.green_white_slider.setValue(self.config.green_white)
        self.green_white_value = QtWidgets.QLabel(str(self.config.green_white))

        # Green gamma slider (0.10 to 3.00 via 10-300)
        self.green_gamma_label = QtWidgets.QLabel("Green Gamma:")
        self.green_gamma_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.green_gamma_slider.setRange(10, 300)
        self.green_gamma_slider.setValue(int(round(self.config.green_gamma * 100)))
        self.green_gamma_value = QtWidgets.QLabel(f"{self.config.green_gamma:.2f}")
        self.green_gamma_value_note = QtWidgets.QLabel("(PS Levels midtone)")

        # Create function to add a row of label+slider+value
        def add_row(parent_layout, label_widget, slider_widget, value_widget=None):
            row = QtWidgets.QHBoxLayout()
            row.addWidget(label_widget)
            row.addWidget(slider_widget)
            if value_widget is not None:
                row.addWidget(value_widget)
            parent_layout.addLayout(row)

        # Create Red Levels section
        red_levels_layout = QtWidgets.QVBoxLayout()
        add_row(red_levels_layout, self.red_min_label, self.red_min_slider, self.red_min_value)
        add_row(red_levels_layout, self.red_max_label, self.red_max_slider, self.red_max_value)
        add_row(red_levels_layout, self.red_gamma_label, self.red_gamma_slider, self.red_gamma_value)

        # Create Green Levels section
        green_levels_layout = QtWidgets.QVBoxLayout()
        add_row(green_levels_layout, self.green_black_label, self.green_black_slider, self.green_black_value)
        add_row(green_levels_layout, self.green_white_label, self.green_white_slider, self.green_white_value)
        add_row(green_levels_layout, self.green_gamma_label, self.green_gamma_slider, self.green_gamma_value)
        note_row = QtWidgets.QHBoxLayout()
        note_row.addStretch(1)
        note_row.addWidget(self.green_gamma_value_note)
        green_levels_layout.addLayout(note_row)

        # Create group boxes for both red and green levels
        red_levels_group = QtWidgets.QGroupBox("Red Levels")
        red_levels_group.setLayout(red_levels_layout)

        green_levels_group = QtWidgets.QGroupBox("Green Levels")
        green_levels_group.setLayout(green_levels_layout)

        # Create a levels container widget to hold both level groups
        levels_container = QtWidgets.QWidget()
        levels_container_layout = QtWidgets.QVBoxLayout(levels_container)
        levels_container_layout.addWidget(red_levels_group)
        levels_container_layout.addWidget(green_levels_group)

        # Remove the unused adjustment group box references since we're using our own levels system
        # Keep the button group for compatibility
        self.adjustments_button_group = QtWidgets.QButtonGroup(self.window)

        # Add output directory to the second row
        output_dir_widget = QtWidgets.QWidget()
        output_dir_widget.setLayout(output_dir_layout)
        second_row_layout.addWidget(output_dir_widget)

        # Create a "Levels" section with its own dedicated area in the layout that can be toggled
        self.levels_container = QtWidgets.QWidget()
        levels_container_layout = QtWidgets.QVBoxLayout(self.levels_container)

        # Create a label to identify the section
        levels_title = QtWidgets.QLabel("Spec Levels")
        levels_title.setStyleSheet("font-weight: bold; font-size: 14px;")

        # Add the title and levels container to the layout
        levels_container_layout.addWidget(levels_title)
        levels_container_layout.addWidget(levels_container)

        # Create wiki area for displaying text content
        self.wiki_area = QtWidgets.QTextEdit()
        self.wiki_area.setReadOnly(True)  # Prevent editing
        self.wiki_area.hide()

        # Layout for add/remove buttons
        add_remove_layout = QtWidgets.QVBoxLayout()
        add_remove_layout.addWidget(self.button_add)
        add_remove_layout.addWidget(self.button_remove)

        # Container for suffix formats
        self.suffix_format_container = QtWidgets.QWidget()
        suffix_format_container_layout = QtWidgets.QVBoxLayout(self.suffix_format_container)
        suffix_format_container_layout.addWidget(suffix_format_scroll_area)
        suffix_format_container_layout.addLayout(add_remove_layout)

        # Add all components to the main layout in the proper order
        main_layout.addLayout(top_row_layout)
        main_layout.addLayout(profile_layout)  # Add profile layout below top row
        main_layout.addLayout(second_row_layout)  # Add second row with output dir
        # Note: levels_section is already added to main_layout above
        # Add the levels container to the main layout
        main_layout.addWidget(self.levels_container)
        main_layout.addWidget(self.log)
        main_layout.addWidget(self.wiki_area)
        main_layout.addWidget(self.suffix_format_container)

        self.window.setLayout(main_layout)
        self.window.setWindowTitle("Universal DDS Auto Converter")
        # Allow the dock widget to shrink more by relaxing size policy
        self.window.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)

        # Connect signals to functions
        self.checkbox.stateChanged.connect(self.checkbox_export_change)
        self.checkbox_overwrite.stateChanged.connect(self.checkbox_overwrite_change)
        self.checkbox_adjust_red.stateChanged.connect(self.checkbox_adjust_red_change)
        self.red_max_slider.valueChanged.connect(self.red_max_slider_change)
        self.red_min_slider.valueChanged.connect(self.red_min_slider_change)
        self.button_texconv.clicked.connect(self.button_texconv_clicked)
        self.button_clear.clicked.connect(self.button_clear_clicked)
        self.button_display_log.clicked.connect(self.toggle_log_display)
        self.button_export_textures.clicked.connect(self.open_export_textures_window)
        self.button_show_wiki.clicked.connect(self.toggle_wiki)
        self.button_toggle_suffix.clicked.connect(self.toggle_suffix_container)
        self.button_toggle_levels.clicked.connect(self.toggle_levels_container)
        self.button_add.clicked.connect(self.add_suffix_format_row)
        self.button_remove.clicked.connect(self.remove_last_suffix_format_row)
        self.button_browse_dir.clicked.connect(self.browse_output_directory)
        self.output_dir_edit.editingFinished.connect(self.output_dir_changed)
        self.red_gamma_slider.valueChanged.connect(self.red_gamma_changed)
        self.green_black_slider.valueChanged.connect(self.green_black_changed)
        self.green_white_slider.valueChanged.connect(self.green_white_changed)
        self.green_gamma_slider.valueChanged.connect(self.green_gamma_changed)

        # Profile management signals
        self.profile_dropdown.currentIndexChanged.connect(self.profile_changed)
        self.button_add_profile.clicked.connect(self.add_profile)
        self.button_delete_profile.clicked.connect(self.delete_profile)

        # Initialize profiles
        self.load_profiles()
        current_profile = self.profile_dropdown.currentText()
        config_profile = config_ini(prompt_texconv_path=False, profile_name=current_profile)
        self.config.suffix_format_map = config_profile.suffix_format_map
        self.load_suffix_formats()

        # Connect the log_signal to the log appending method
        self.log_signal.connect(self.log.append)

        # Setup custom Qt logging handler
        self.setup_logging()

        # Apply initial visibility states
        if not self.config.show_suffixes:
            self.suffix_format_container.hide()
            self.button_toggle_suffix.setText("Show Suffixes")

        if not self.config.show_levels:
            self.levels_container.hide()
            self.button_toggle_levels.setText("Show Levels")
            
        # Apply log visibility state
        if not self.config.show_log:
            self.log.hide()
            self.button_display_log.setText("Show Log")
        
        # Apply wiki visibility state
        if self.config.show_wiki:
            # Load the wiki content and show it
            wiki_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wiki.txt")
            if os.path.exists(wiki_file_path):
                try:
                    with open(wiki_file_path, 'r', encoding='utf-8') as wiki_file:
                        self.wiki_area.setPlainText(wiki_file.read())
                    self.wiki_area.show()
                    self.button_show_wiki.setText("Hide Wiki")
                except Exception:
                    # If there's an error loading the wiki, keep it hidden
                    self.wiki_area.hide()
                    self.button_show_wiki.setText("Show Wiki")
                    self.show_wiki = False
            else:
                # If wiki.txt doesn't exist, keep it hidden
                self.wiki_area.hide()
                self.button_show_wiki.setText("Show Wiki")
                self.show_wiki = False

        # Add the window to the Substance Painter UI
        substance_painter.ui.add_dock_widget(self.window)
        self.log_signal.emit(f"TexConv Path: {self.config.texconv_path}")
        self.log_signal.emit(f"Current Profile: {current_profile}")
        self.log_signal.emit(f"Output Directory: {self.config.output_dir if self.config.output_dir else 'Same as source file'}")

        # Connect export event handler
        connections = {
            substance_painter.event.ExportTexturesEnded: self.on_export_finished
        }
        for event, callback in connections.items():
            substance_painter.event.DISPATCHER.connect(event, callback)

    def browse_output_directory(self):
        """Open a dialog to select the output directory."""
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(
            self.window, "Select Output Directory", self.config.output_dir if self.config.output_dir else "")

        if dir_path:
            self.output_dir_edit.setText(dir_path)
            self.config.output_dir = dir_path
            self.save_config()
            self.log_signal.emit(f"Output directory set to: {self.config.output_dir}")

    def output_dir_changed(self):
        """Handle manual changes to the output directory text field."""
        new_dir = self.output_dir_edit.text().strip()
        if new_dir != self.config.output_dir:
            self.config.output_dir = new_dir
            self.save_config()
            self.log_signal.emit(
                f"Output directory set to: {self.config.output_dir if self.config.output_dir else 'Same as source file'}")

    def toggle_suffix_container(self):
        if self.suffix_format_container.isVisible():
            self.suffix_format_container.hide()
            self.button_toggle_suffix.setText("Show Suffixes")
            self.config.show_suffixes = False
        else:
            self.suffix_format_container.show()
            self.button_toggle_suffix.setText("Hide Suffixes")
            self.config.show_suffixes = True
        self.save_config()

    def toggle_levels_container(self):
        if self.levels_container.isVisible():
            self.levels_container.hide()
            self.button_toggle_levels.setText("Show Levels")
            self.config.show_levels = False
        else:
            self.levels_container.show()
            self.button_toggle_levels.setText("Hide Levels")
            self.config.show_levels = True
        self.save_config()

    def setup_logging(self):
        """Sets up the custom Qt logging handler to direct logs to QTextEdit."""
        # Remove all existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        # Create and add the custom Qt handler
        qt_handler = QtLogHandler()
        qt_handler.log_message.connect(self.log.append)  # Connect renamed signal
        logger.addHandler(qt_handler)

        # Set the logging level
        logger.setLevel(logging.DEBUG)

    # Profile management methods

    # Method to load profiles into the dropdown
    def load_profiles(self):
        ini_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "Universal-DDS-Exporter-PluginSettings.ini")
        config = configparser.ConfigParser()
        config.optionxform = str
        profiles = []

        if os.path.exists(ini_file_path):
            config.read(ini_file_path)
            # Profiles are sections ending with '_SuffixFormats'
            profiles = [section[:-len('_SuffixFormats')] for section in config.sections() if
                        section.endswith('_SuffixFormats')]

        if not profiles:
            profiles = ["Default"]
            # Ensure Default_SuffixFormats exists
            if "Default_SuffixFormats" not in config:
                config["Default_SuffixFormats"] = {}
                with open(ini_file_path, 'w') as configfile:
                    config.write(configfile)

        self.profile_dropdown.clear()
        self.profile_dropdown.addItems(profiles)

    # Method to handle profile changes
    def profile_changed(self, index):
        profile_name = self.profile_dropdown.currentText()
        self.updating_ui = True  # Start UI update
        self.config = config_ini(prompt_texconv_path=False, profile_name=profile_name)
        # Update UI elements based on the new profile
        self.load_suffix_formats()
        self.checkbox_adjust_red.setChecked(self.config.adjust_red)
        # Update min/max sliders and labels
        self.red_min_slider.setValue(self.config.red_min)
        self.red_min_value.setText(str(self.config.red_min))
        self.red_max_slider.setValue(self.config.red_max)
        self.red_max_value.setText(str(self.config.red_max))
        # Update green levels UI (now sliders) + gamma labels
        if hasattr(self, 'red_gamma_slider'):
            self.red_gamma_slider.setValue(int(round(self.config.red_gamma * 100)))
            self.red_gamma_value.setText(f"{self.config.red_gamma:.2f}")
        if hasattr(self, 'green_black_slider'):
            self.green_black_slider.setValue(self.config.green_black)
            self.green_black_value.setText(str(self.config.green_black))
        if hasattr(self, 'green_white_slider'):
            self.green_white_slider.setValue(self.config.green_white)
            self.green_white_value.setText(str(self.config.green_white))
        if hasattr(self, 'green_gamma_slider'):
            self.green_gamma_slider.setValue(int(round(self.config.green_gamma * 100)))
            self.green_gamma_value.setText(f"{self.config.green_gamma:.2f}")

        # Ensure min < max
        if self.config.red_min >= self.config.red_max:
            self.config.red_min = self.config.red_max - 1
            self.red_min_slider.setValue(self.config.red_min)
            self.red_min_value.setText(str(self.config.red_min))

        self.log_signal.emit(f"Switched to profile: {profile_name}")
        self.updating_ui = False  # End UI update

    # Method to add a new profile
    def add_profile(self):
        text, ok = QtWidgets.QInputDialog.getText(self.window, 'Add Profile', 'Enter new profile name:')
        if ok and text:
            profile_name = text.strip()
            if not profile_name:
                QtWidgets.QMessageBox.warning(self.window, "Invalid Name", "Profile name cannot be empty.")
                return
            if profile_name in [self.profile_dropdown.itemText(i) for i in range(self.profile_dropdown.count())]:
                QtWidgets.QMessageBox.warning(self.window, "Duplicate Profile",
                                              f"The profile '{profile_name}' already exists.")
                return
            # Initialize the new profile with empty suffix formats
            self.config = config_ini(prompt_texconv_path=False, profile_name=profile_name)
            # Keep show_log and show_wiki state from previous config
            self.load_profiles()
            self.profile_dropdown.setCurrentText(profile_name)
            self.save_config()
            self.log_signal.emit(f"Added new profile: {profile_name}")

    # Method to delete the selected profile
    def delete_profile(self):
        profile_name = self.profile_dropdown.currentText()
        if profile_name == "Default":
            QtWidgets.QMessageBox.warning(self.window, "Cannot Delete", "The 'Default' profile cannot be deleted.")
            return
        reply = QtWidgets.QMessageBox.question(
            self.window,
            'Delete Profile',
            f"Are you sure you want to delete the profile '{profile_name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            ini_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "Universal-DDS-Exporter-PluginSettings.ini")
            config = configparser.ConfigParser()
            config.optionxform = str
            if os.path.exists(ini_file_path):
                config.read(ini_file_path)
                suffix_section = f"{profile_name}_SuffixFormats"
                if suffix_section in config:
                    config.remove_section(suffix_section)
                with open(ini_file_path, 'w') as configfile:
                    config.write(configfile)
                self.load_profiles()
                self.profile_dropdown.setCurrentIndex(0)
                self.save_config()
                self.log_signal.emit(f"Deleted profile: {profile_name}")

    # Toggle the wiki visibility
    def toggle_wiki(self):
        if self.wiki_area.isVisible():
            self.wiki_area.hide()
            self.button_show_wiki.setText("Show Wiki")
            self.config.show_wiki = False
        else:
            # Load the text from a .txt file
            wiki_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wiki.txt")
            if os.path.exists(wiki_file_path):
                try:
                    with open(wiki_file_path, 'r', encoding='utf-8') as wiki_file:
                        self.wiki_area.setPlainText(wiki_file.read())
                except Exception as e:
                    QtWidgets.QMessageBox.critical(self.window, "Error", f"Failed to load wiki.txt: {e}")
                    return
            else:
                QtWidgets.QMessageBox.warning(self.window, "Missing File", "wiki.txt not found.")
                return

            self.wiki_area.show()
            self.button_show_wiki.setText("Hide Wiki")
            self.config.show_wiki = True
        self.save_config()

    # Function to simulate Ctrl+Shift+E to open the export window
    def open_export_textures_window(self):
        event = QKeyEvent(QEvent.KeyPress, Qt.Key_E, Qt.ControlModifier | Qt.ShiftModifier)
        QtWidgets.QApplication.sendEvent(substance_painter.ui.get_main_window(), event)

    # Add a new suffix format row to the UI
    def add_suffix_format_row(self, suffix="", format_option="BC7_UNORM", is_loading=False):
        if not is_loading:
            if suffix:
                if suffix in self.suffix_format_map:
                    QtWidgets.QMessageBox.warning(
                        self.window,
                        "Duplicate Suffix",
                        f"The suffix '{suffix}' already exists. Please use a unique suffix."
                    )
                    return  # Do not add the duplicate row

        # Create a widget for the row
        row_widget = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row_widget)

        # Create the suffix input and format dropdown
        suffix_input = QtWidgets.QLineEdit()
        suffix_input.setPlaceholderText("Suffix")
        suffix_input.setText(suffix)
        if suffix:
            suffix_input.original_suffix = suffix  # Initialize original_suffix
        format_dropdown = QtWidgets.QComboBox()
        format_dropdown.addItems([
            "BC1_UNORM",
            "BC1_UNORM_SRGB",
            "BC1_ALPHA_UNORM",
            "BC1_ALPHA_UNORM_SRGB",
            "BC2_UNORM",
            "BC2_UNORM_SRGB",
            "BC3_UNORM",
            "BC3_UNORM_SRGB",
            "BC4_UNORM",
            "BC4_SNORM",
            "BC5_UNORM",
            "BC5_SNORM",
            "BC6H_UF16",
            "BC6H_SF16",
            "BC7_UNORM",
            "BC7_UNORM_SRGB",
            "R32G32B32A32_FLOAT",
            "R32G32B32_FLOAT",
            "R16G16B16A16_FLOAT",
            "R16G16B16A16_UNORM",
            "R16G16B16A16_SNORM",
            "R32G32_FLOAT",
            "R10G10B10A2_UNORM",
            "R11G11B10_FLOAT",
            "R8G8B8A8_UNORM",
            "R8G8B8A8_UNORM_SRGB",
            "R8G8B8A8_SNORM",
            "R16G16_FLOAT",
            "R16G16_UNORM",
            "R16G16_SNORM",
            "R32_FLOAT",
            "R8G8_UNORM",
            "R8G8_SNORM",
            "R16_FLOAT",
            "R16_UNORM",
            "R16_SNORM",
            "R8_UNORM",
            "R8_SNORM",
            "A8_UNORM",
            "R8G8_B8G8_UNORM",
            "G8R8_G8B8_UNORM",
            "B5G6R5_UNORM",
            "B5G5R5A1_UNORM",
            "B8G8R8A8_UNORM",
            "B8G8R8X8_UNORM",
            "B8G8R8A8_UNORM_SRGB",
            "B8G8R8X8_UNORM_SRGB",
            "B4G4R4A4_UNORM",
            "A4B4G4R4_UNORM",
            "BC3n"
        ])
        index = format_dropdown.findText(format_option)
        if index != -1:
            format_dropdown.setCurrentIndex(index)

        # Add the widgets to the row layout
        row_layout.addWidget(suffix_input)
        row_layout.addWidget(format_dropdown)

        # Add the row widget to the suffix_format_layout
        self.suffix_format_layout.addWidget(row_widget)

        # Connect signals with partial functions to pass widgets
        suffix_input.editingFinished.connect(partial(self.handle_suffix_edit, suffix_input, format_dropdown))
        # Ensure the callback receives the index parameter
        format_dropdown.currentIndexChanged.connect(partial(self.handle_format_change, suffix_input, format_dropdown))

    # Handle suffix edits (QLineEdit)
    def handle_suffix_edit(self, suffix_input, format_dropdown):
        if self.updating_ui:
            return  # Ignore changes during UI updates
        suffix_text = suffix_input.text().strip()

        if not suffix_text:
            QtWidgets.QMessageBox.warning(self.window, "Invalid Suffix", "Suffix cannot be empty.")
            # Remove the invalid row from UI
            row_widget = suffix_input.parent()
            self.suffix_format_layout.removeWidget(row_widget)
            self.remove_widgets_from_layout(row_widget.layout())
            row_widget.deleteLater()
            return

        existing_suffixes = set(self.suffix_format_map.keys())
        # Remove the current suffix from the existing set to allow renaming to itself
        if hasattr(suffix_input, 'original_suffix'):
            existing_suffixes.discard(suffix_input.original_suffix)

        # Check for duplicate suffix
        if suffix_text in existing_suffixes:
            QtWidgets.QMessageBox.warning(
                self.window,
                "Duplicate Suffix",
                f"The suffix '{suffix_text}' already exists. Please use a unique suffix."
            )
            # Remove the duplicate row from UI
            row_widget = suffix_input.parent()
            self.suffix_format_layout.removeWidget(row_widget)
            self.remove_widgets_from_layout(row_widget.layout())
            row_widget.deleteLater()
            return

        # Update the mapping
        if hasattr(suffix_input, 'original_suffix'):
            original_suffix = suffix_input.original_suffix
            if original_suffix in self.suffix_format_map:
                del self.suffix_format_map[original_suffix]

        suffix_input.original_suffix = suffix_text  # Update the original suffix

        if suffix_text:
            # Add or update the suffix and format in the suffix_format_map
            selected_format = format_dropdown.currentText()
            self.suffix_format_map[suffix_text] = selected_format

            # Update the .ini file
            self.save_config()

            self.log_signal.emit(f"Added/Updated suffix '{suffix_text}' with format '{selected_format}'.")

    # Handle format changes (QComboBox)
    def handle_format_change(self, suffix_input, format_dropdown, index):
        if self.updating_ui:
            return  # Ignore changes during UI updates
        suffix_text = suffix_input.text().strip()

        if not suffix_text:
            # Optionally, do nothing or notify user
            return

        # Update the format in the suffix_format_map
        selected_format = format_dropdown.currentText()
        self.suffix_format_map[suffix_text] = selected_format

        # Update the .ini file
        self.save_config()

        self.log_signal.emit(f"Updated format for suffix '{suffix_text}' to '{selected_format}'.")

    # Remove the last suffix format row and delete the associated suffix from the config
    def remove_last_suffix_format_row(self):
        if self.suffix_format_layout.count() > 0:
            # Remove the last row widget
            last_row_index = self.suffix_format_layout.count() - 1
            last_row_item = self.suffix_format_layout.itemAt(last_row_index)
            last_row_widget = last_row_item.widget()
            if last_row_widget:
                # Get the suffix from the input
                suffix_input = last_row_widget.findChild(QtWidgets.QLineEdit)
                if suffix_input:
                    suffix = suffix_input.text().strip()
                    if suffix in self.suffix_format_map:
                        del self.suffix_format_map[suffix]

                        # Remove from config file
                        self.save_config()
                        self.log_signal.emit(f"Removed suffix '{suffix}' from config.")

                # Remove the widget from the layout and delete it
                self.suffix_format_layout.removeWidget(last_row_widget)
                self.remove_widgets_from_layout(last_row_widget.layout())
                last_row_widget.deleteLater()

    # Helper method to remove widgets from a layout
    def remove_widgets_from_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif isinstance(child, QtWidgets.QLayout):
                self.remove_widgets_from_layout(child)
        layout.deleteLater()

    # Handle TexConv location button click
    def button_texconv_clicked(self):
        # Allow user to choose TexConv path and update global setting
        new_path = choose_texconv_executable()
        if new_path:
            self.config.texconv_path = new_path
            self.save_config()
            self.log_signal.emit(f"Updated TexConv Path: {self.config.texconv_path}")
        else:
            self.log_signal.emit("TexConv path update canceled.")

    # Clear the log window
    def button_clear_clicked(self):
        self.log.clear()

    # Toggle the log display visibility
    def toggle_log_display(self):
        if self.log.isVisible():
            self.log.hide()
            self.button_display_log.setText("Show Log")
            self.config.show_log = False
        else:
            self.log.show()
            self.button_display_log.setText("Hide Log")
            self.config.show_log = True
        self.save_config()

    # Handle export DDS files checkbox change
    def checkbox_export_change(self, state):
        self.config.export_dds = self.checkbox.isChecked()  # Corrected: Use isChecked()
        self.save_config()
        self.log_signal.emit(f"Export DDS Files set to: {self.config.export_dds}")

    # Handle overwrite DDS files checkbox change
    def checkbox_overwrite_change(self, state):
        self.config.overwrite_dds = self.checkbox_overwrite.isChecked()  # Corrected: Use isChecked()
        self.save_config()
        self.log_signal.emit(f"Overwrite DDS Files set to: {self.config.overwrite_dds}")

    # Handle adjust specular red checkbox change
    def checkbox_adjust_red_change(self, state):
        self.config.adjust_red = self.checkbox_adjust_red.isChecked()
        self.save_config()
        self.log_signal.emit(f"Fallout 4 Spec Adjustments enabled: {self.config.adjust_red}")

    # Add handler methods
    def red_min_slider_change(self, value):
        # Ensure min is always less than max
        if value >= self.red_max_slider.value():
            value = self.red_max_slider.value() - 1
            self.red_min_slider.setValue(value)

        self.config.red_min = value
        self.red_min_value.setText(str(value))
        self.save_config()

    def red_max_slider_change(self, value):
        # Ensure max is always greater than min
        if value <= self.red_min_slider.value():
            value = self.red_min_slider.value() + 1
            self.red_max_slider.setValue(value)

        self.config.red_max = value
        self.red_max_value.setText(str(value))
        self.save_config()

    def red_gamma_changed(self, value):
        # Slider 10-300 maps to 0.10-3.00
        self.config.red_gamma = round(max(10, min(300, int(value))) / 100.0, 2)
        self.red_gamma_value.setText(f"{self.config.red_gamma:.2f}")
        self.save_config()

    def green_black_changed(self, value):
        # Ensure black is less than white
        if value >= self.config.green_white:
            value = max(0, self.config.green_white - 1)
            self.green_black_slider.setValue(value)
        self.config.green_black = int(value)
        self.green_black_value.setText(str(self.config.green_black))
        self.save_config()

    def green_white_changed(self, value):
        # Ensure white is greater than black
        if value <= self.config.green_black:
            value = min(255, self.config.green_black + 1)
            self.green_white_slider.setValue(value)
        self.config.green_white = int(value)
        self.green_white_value.setText(str(self.config.green_white))
        self.save_config()

    def green_gamma_changed(self, value):
        # Slider 10-300 maps to 0.10-3.00
        self.config.green_gamma = round(max(10, min(300, int(value))) / 100.0, 2)
        self.green_gamma_value.setText(f"{self.config.green_gamma:.2f}")
        self.save_config()

    # Save the current plugin configuration to the ini file
    def save_config(self):
        ini_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "Universal-DDS-Exporter-PluginSettings.ini")
        config = configparser.ConfigParser()
        config.optionxform = str  # Preserve case of options

        config.read(ini_file_path)

        # Save global settings
        config['General']['TexConvDirectory'] = self.config.texconv_path
        config['General']['ExportDDSFiles'] = str(self.config.export_dds)
        config['General']['OverwriteDDSFiles'] = str(self.config.overwrite_dds)
        config['General']['AdjustSpecularRed'] = str(self.config.adjust_red)
        config['General']['RedMaxValue'] = str(self.config.red_max)
        config['General']['RedMinValue'] = str(self.config.red_min)
        config['General']['RedGamma'] = str(self.config.red_gamma)
        config['General']['GreenBlack'] = str(self.config.green_black)
        config['General']['GreenGamma'] = str(self.config.green_gamma)
        config['General']['GreenWhite'] = str(self.config.green_white)
        config['General']['OutputDir'] = self.config.output_dir

        # Save visibility states
        config['General']['ShowSuffixes'] = str(self.config.show_suffixes)
        config['General']['ShowLevels'] = str(self.config.show_levels)
        config['General']['ShowLog'] = str(self.config.show_log)
        config['General']['ShowWiki'] = str(self.config.show_wiki)

        # Save suffix formats for the current profile
        profile_name = self.profile_dropdown.currentText()
        suffix_section = f"{profile_name}_SuffixFormats"

        if suffix_section not in config:
            config[suffix_section] = {}

        # Clear existing suffix formats for the profile
        config.remove_section(suffix_section)
        config.add_section(suffix_section)

        for suffix, format_option in self.config.suffix_format_map.items():
            config[suffix_section][suffix] = format_option

        # Write updated config to the ini file
        with open(ini_file_path, 'w') as configfile:
            config.write(configfile)

    # Load suffix formats from the ini file into the UI
    def load_suffix_formats(self):
        self.updating_ui = True  # Start UI update

        # Clear existing suffix format UI
        while self.suffix_format_layout.count():
            child = self.suffix_format_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif isinstance(child, QtWidgets.QLayout):
                # Recursively delete layouts
                self.remove_widgets_from_layout(child)

        # Add suffix formats from the map
        for suffix, format_option in self.config.suffix_format_map.items():
            self.add_suffix_format_row(suffix, format_option, is_loading=True)

        self.updating_ui = False  # End UI update

    # Cleanup function when the plugin is unloaded
    def cleanup(self):
        if self.is_cleaned_up:
            logger.info("Cleanup has already been performed.")
            return  # Prevent multiple cleanups

        # Disconnect signals
        try:
            self.checkbox.stateChanged.disconnect(self.checkbox_export_change)
            self.checkbox_overwrite.stateChanged.disconnect(self.checkbox_overwrite_change)
            self.checkbox_adjust_red.stateChanged.disconnect(self.checkbox_adjust_red_change)
            self.red_max_slider.valueChanged.disconnect(self.red_max_slider_change)
            self.button_texconv.clicked.disconnect(self.button_texconv_clicked)
            self.button_clear.clicked.disconnect(self.button_clear_clicked)
            self.button_display_log.clicked.disconnect(self.toggle_log_display)
            self.button_export_textures.clicked.disconnect(self.open_export_textures_window)
            self.button_show_wiki.clicked.disconnect(self.toggle_wiki)
            self.button_toggle_suffix.clicked.disconnect(self.toggle_suffix_container)
            self.button_toggle_levels.clicked.disconnect(self.toggle_levels_container)
            self.button_add.clicked.disconnect(self.add_suffix_format_row)
            self.button_remove.clicked.disconnect(self.remove_last_suffix_format_row)
            self.button_browse_dir.clicked.disconnect(self.browse_output_directory)
            self.output_dir_edit.editingFinished.disconnect(self.output_dir_changed)
            if hasattr(self, 'red_gamma_slider'):
                self.red_gamma_slider.valueChanged.disconnect(self.red_gamma_changed)
            if hasattr(self, 'green_black_slider'):
                self.green_black_slider.valueChanged.disconnect(self.green_black_changed)
            if hasattr(self, 'green_white_slider'):
                self.green_white_slider.valueChanged.disconnect(self.green_white_changed)
            if hasattr(self, 'green_gamma_slider'):
                self.green_gamma_slider.valueChanged.disconnect(self.green_gamma_changed)
            self.profile_dropdown.currentIndexChanged.disconnect(self.profile_changed)
            self.button_add_profile.clicked.disconnect(self.add_profile)
            self.button_delete_profile.clicked.disconnect(self.delete_profile)
            self.log_signal.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting signals: {e}")

        # Remove the dock widget using the correct method
        try:
            if self.window:
                substance_painter.ui.delete_ui_element(self.window)
                logger.info("Dock widget successfully deleted.")
        except AttributeError as e:
            logger.error(f"Error deleting UI element: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during UI element deletion: {e}")

        # Set widget references to None to prevent access to deleted objects
        self.window = None
        self.log = None
        self.wiki_area = None
        self.profile_dropdown = None
        self.button_add_profile = None
        self.button_delete_profile = None

        # Mark as cleaned up
        self.is_cleaned_up = True

    # Handle export finished event from Substance Painter
    def on_export_finished(self, res):
        log.info("Export finished.")
        if not self.config.export_dds:
            self.log_signal.emit("DDS export is disabled. No files will be processed.")
            return

        self.log_signal.emit(res.message)
        self.log_signal.emit("Exported files:")

        for file_list in res.textures.values():
            for file_path in file_list:
                self.log_signal.emit(f"  {file_path}")

        self.log_signal.emit("Converting to DDS files:")

        suffix_format_map = self.get_suffix_format_map()

        for file_list in res.textures.values():
            for file_path in file_list:
                if file_path.endswith(".png") or file_path.endswith(".tga"):
                    result_message = convert_png_to_dds(
                        self.config, file_path, suffix_format_map
                    )
                    if result_message:
                        self.log_signal.emit(f"  {result_message}")

        log.info("Conversion Complete.")

    # Helper function to get the suffix format map from the UI
    def get_suffix_format_map(self):
        return self.config.suffix_format_map.copy()

    # Handle export error event
    def on_export_error(self, err):
        self.log_signal.emit("Export failed.")
        self.log_signal.emit(repr(err))


# Global plugin instance
Universal_DDS_PLUGIN: 'UniversalDDSPlugin' = None


# Function called when the plugin is started
def start_plugin():
    """This method is called when the plugin is started."""
    log.info("Universal DDS Exporter Plugin Initialized")
    global Universal_DDS_PLUGIN
    Universal_DDS_PLUGIN = UniversalDDSPlugin()


# Function called when the plugin is closed
def close_plugin():
    """This method is called when the plugin is stopped."""
    log.info("Universal DDS Exporter Plugin Shutdown")
    global Universal_DDS_PLUGIN
    if Universal_DDS_PLUGIN:
        Universal_DDS_PLUGIN.cleanup()
        Universal_DDS_PLUGIN = None


if __name__ == "__main__":
    start_plugin()
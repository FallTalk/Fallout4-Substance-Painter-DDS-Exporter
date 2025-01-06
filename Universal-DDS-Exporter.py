__author__ = "Emil Eldstål"
__copyright__ = "Copyright 2023, Emil Eldstål"
__version__ = "0.1.1"
__forkedVersion__ = "1.0.4"
__painterVersion__ = "10.1.2"

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

import os
import configparser
import subprocess
from functools import partial
import logging

# Remove the basicConfig call to prevent default handlers
# logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Define the default TexConv path
DEFAULT_TEXCONV_PATH = "C:\\DirectXTex\\Texconv\\texconv.exe"

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
            QtWidgets.QMessageBox.warning(main_window, "Invalid Path", "texconv.exe not found in the selected directory.")
            return ""
    else:
        return ""  # Return empty string if no directory is selected

# Function to load and update settings from the ini configuration file
def config_ini(prompt_texconv_path, profile_name=None):
    # Get the path to the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define the path to the Universal-DDS-Exporter-PluginSettings.ini file
    ini_file_path = os.path.join(script_dir, "Universal-DDS-Exporter-PluginSettings.ini")
    
    # Create a ConfigParser object
    config = configparser.ConfigParser()
    config.optionxform = str  # Preserve case of options

    # If INI file doesn't exist, create it with default [General] section
    if not os.path.exists(ini_file_path):
        config['General'] = {
            'TexConvDirectory': DEFAULT_TEXCONV_PATH,
            'ExportDDSFiles': 'False',
            'OverwriteDDSFiles': 'False'
        }
        with open(ini_file_path, 'w') as configfile:
            config.write(configfile)

    # Read the INI file with error handling
    try:
        config.read(ini_file_path)
    except configparser.ParsingError as e:
        logger.error(f"INI parsing error: {e}")
        QtWidgets.QMessageBox.critical(None, "Configuration Error", "The configuration file is corrupted and will be reset to default settings.")
        # Reset to default settings
        config = configparser.ConfigParser()
        config.optionxform = str
        config['General'] = {
            'TexConvDirectory': DEFAULT_TEXCONV_PATH,
            'ExportDDSFiles': 'False',
            'OverwriteDDSFiles': 'False'
        }
        with open(ini_file_path, 'w') as configfile:
            config.write(configfile)
        profile_name = None  # Reset profile if necessary

    # Ensure [General] section exists
    if 'General' not in config:
        config['General'] = {
            'TexConvDirectory': DEFAULT_TEXCONV_PATH,
            'ExportDDSFiles': 'False',
            'OverwriteDDSFiles': 'False'
        }

    # Update TexConv path if prompt_texconv_path is True
    if prompt_texconv_path:
        new_texconv_path = choose_texconv_executable()
        if new_texconv_path:
            config['General']['TexConvDirectory'] = new_texconv_path
        else:
            # If user cancels the dialog, retain the existing path
            pass

    # Assign global settings
    TexConvPath = config['General'].get('TexConvDirectory', DEFAULT_TEXCONV_PATH)
    export_state = config.getboolean('General', 'ExportDDSFiles', fallback=False)
    overwrite_state = config.getboolean('General', 'OverwriteDDSFiles', fallback=False)

    # Handle profiles if profile_name is provided
    suffix_format_map = {}
    if profile_name:
        suffix_section = f"{profile_name}_SuffixFormats"
        if suffix_section in config:
            items = config.items(suffix_section)
            # Detect duplicates
            seen = set()
            for key, value in items:
                if key in seen:
                    logger.warning(f"Duplicate suffix '{key}' found in configuration. Ignoring subsequent entries.")
                    continue  # Skip duplicates
                seen.add(key)
                suffix_format_map[key] = value
        else:
            # Create the profile section if it doesn't exist
            config[suffix_section] = {}
            with open(ini_file_path, 'w') as configfile:
                config.write(configfile)

    return TexConvPath, export_state, overwrite_state, suffix_format_map

# Function to convert PNG files to DDS format using TexConv
def convert_png_to_dds(texconvPath, sourcePNG, overwrite, suffix_format_map):
    if not texconvPath or not os.path.exists(texconvPath):
        logger.error("Invalid TexConv path.")
        return "Invalid TexConv path."
    
    sourceFolder = os.path.dirname(sourcePNG)
    outputFolder = os.path.join(sourceFolder, "DDS")
    outputFile = os.path.join(outputFolder, os.path.splitext(os.path.basename(sourcePNG))[0] + ".dds")

    # Ensure DDS subfolder exists
    if not os.path.exists(outputFolder):
        # Create the DDS directory if it does not exist
        os.makedirs(outputFolder)
        logger.info("Created DDS subfolder")

    filename = os.path.basename(sourcePNG)
    if filename.endswith(".png"):
        sourceFile = os.path.splitext(filename)[0]

        # Extract suffix and choose corresponding DDS format from suffix_format_map
        if '_' in sourceFile:
            suffix = sourceFile.rsplit('_', 1)[-1].rstrip('_')
            if not suffix:
                QtWidgets.QMessageBox.warning(None, "Invalid Suffix", f"No valid suffix found in '{filename}'. Using default format.")
                format_option = "BC7_UNORM"
            else:
                format_option = suffix_format_map.get(suffix, "BC7_UNORM")
        else:
            # If no suffix defined
            suffix = None
            format_option = "BC7_UNORM"

        logger.info(f"Processing {filename}")
        logger.info(f"Extracted suffix: {suffix}")
        logger.info(f"Chosen format: {format_option}")

        # Set overwrite_option based on the state
        overwrite_option = ["-y"] if overwrite else []

        # Check if DDS file already exists and if overwrite is disabled
        if overwrite or not os.path.exists(outputFile):
            texconv_cmd = [
                texconvPath,
                "-nologo",
            ] + overwrite_option + [
                "-o", outputFolder,
                "-f", format_option,
                os.path.join(sourceFolder, filename)
            ]

            logger.debug(f"Running command: {' '.join(texconv_cmd)}")

            # Run TexConv command
            try:
                subprocess.run(texconv_cmd, shell=False, check=True)
                logger.info(f"Successfully converted {filename} to {outputFile} using {format_option}")
                return f"Converted {filename} to {outputFile} with format {format_option}"
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to convert {filename}: {e}")
                return f"Failed to convert {filename}"
        else:
            logger.info(f"Skipping conversion for {filename}, DDS file already exists and overwrite is disabled.")
            return f"Skipping conversion for {filename}, DDS file already exists."

    return ""

# Custom Qt Logging Handler
class QtLogHandler(QObject, logging.Handler):
    log_message = Signal(str)  # Renamed signal to avoid conflicts

    def __init__(self):
        super().__init__()
        logging.Handler.__init__(self)  # Explicitly initialize logging.Handler
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_message.emit(msg)
        except Exception as e:
            print(f"Logging emit error: {e}")

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
        self.TexConvPath, self.export, self.overwrite, _ = config_ini(prompt_texconv_path=False)
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
        suffix_format_scroll_area.setMinimumWidth(300)

        # Buttons
        self.checkbox = QtWidgets.QCheckBox("Export DDS files")
        self.checkbox.setChecked(self.export)
        self.checkbox_overwrite = QtWidgets.QCheckBox("Overwrite DDS files")
        self.checkbox_overwrite.setChecked(self.overwrite)
        self.button_texconv = QtWidgets.QPushButton("Texconv location")
        self.button_clear = QtWidgets.QPushButton("Clear Log")
        self.button_display_log = QtWidgets.QPushButton("Hide Log")
        self.button_show_wiki = QtWidgets.QPushButton("Wiki")
        self.button_export_textures = QtWidgets.QPushButton("Export Textures")

        # Version label
        version_label = QtWidgets.QLabel(f"Version: {self.version}")
        
        # Buttons to add or remove suffix formats
        self.button_add = QtWidgets.QPushButton("Add")
        self.button_remove = QtWidgets.QPushButton("Remove")
        
        # Add widgets to top row layout
        top_row_layout.addWidget(self.checkbox)
        top_row_layout.addWidget(self.checkbox_overwrite)
        top_row_layout.addWidget(self.button_texconv)
        top_row_layout.addWidget(self.button_clear)
        top_row_layout.addWidget(self.button_display_log)
        top_row_layout.addWidget(self.button_export_textures)
        top_row_layout.addWidget(self.button_show_wiki)
        top_row_layout.addWidget(version_label)
        
        # Create wiki area for displaying text content
        self.wiki_area = QtWidgets.QTextEdit()
        self.wiki_area.setReadOnly(True)  # Prevent editing
        self.wiki_area.hide()

        # Layout for add/remove buttons
        add_remove_layout = QtWidgets.QVBoxLayout()
        add_remove_layout.addWidget(self.button_add)
        add_remove_layout.addWidget(self.button_remove)

        # Container for suffix formats
        suffix_format_container = QtWidgets.QWidget()
        suffix_format_container_layout = QtWidgets.QVBoxLayout(suffix_format_container)
        suffix_format_container_layout.addWidget(suffix_format_scroll_area)
        suffix_format_container_layout.addLayout(add_remove_layout)

        # Add all components to the main layout
        main_layout.addLayout(top_row_layout)
        main_layout.addLayout(profile_layout)  # Add profile layout below top row
        main_layout.addWidget(self.log)
        main_layout.addWidget(self.wiki_area)
        main_layout.addWidget(suffix_format_container)

        self.window.setLayout(main_layout)
        self.window.setWindowTitle("Universal DDS Auto Converter")

        # Connect signals to functions
        self.checkbox.stateChanged.connect(self.checkbox_export_change)
        self.checkbox_overwrite.stateChanged.connect(self.checkbox_overwrite_change)
        self.button_texconv.clicked.connect(self.button_texconv_clicked)
        self.button_clear.clicked.connect(self.button_clear_clicked)
        self.button_display_log.clicked.connect(self.toggle_log_display)
        self.button_export_textures.clicked.connect(self.open_export_textures_window)
        self.button_show_wiki.clicked.connect(self.toggle_wiki)
        self.button_add.clicked.connect(self.add_suffix_format_row)
        self.button_remove.clicked.connect(self.remove_last_suffix_format_row)

        # Profile management signals
        self.profile_dropdown.currentIndexChanged.connect(self.profile_changed)
        self.button_add_profile.clicked.connect(self.add_profile)
        self.button_delete_profile.clicked.connect(self.delete_profile)

        # Initialize profiles
        self.load_profiles()
        current_profile = self.profile_dropdown.currentText()
        _, _, _, self.suffix_format_map = config_ini(prompt_texconv_path=False, profile_name=current_profile)
        self.load_suffix_formats()

        # Connect the log_signal to the log appending method
        self.log_signal.connect(self.log.append)

        # Setup custom Qt logging handler
        self.setup_logging()

        # Add the window to the Substance Painter UI
        substance_painter.ui.add_dock_widget(self.window)
        self.log.append(f"TexConv Path: {self.TexConvPath}")
        self.log.append(f"Current Profile: {current_profile}")

        # Connect export event handler
        connections = {
            substance_painter.event.ExportTexturesEnded: self.on_export_finished
        }
        for event, callback in connections.items():
            substance_painter.event.DISPATCHER.connect(event, callback)
            
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
        ini_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Universal-DDS-Exporter-PluginSettings.ini")
        config = configparser.ConfigParser()
        config.optionxform = str
        profiles = []

        if os.path.exists(ini_file_path):
            config.read(ini_file_path)
            # Profiles are sections ending with '_SuffixFormats'
            profiles = [section[:-len('_SuffixFormats')] for section in config.sections() if section.endswith('_SuffixFormats')]

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
        _, _, _, self.suffix_format_map = config_ini(prompt_texconv_path=False, profile_name=profile_name)
        # Update UI elements based on the new profile
        self.load_suffix_formats()
        self.log.append(f"Switched to profile: {profile_name}")
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
                QtWidgets.QMessageBox.warning(self.window, "Duplicate Profile", f"The profile '{profile_name}' already exists.")
                return
            # Initialize the new profile with empty suffix formats
            _, _, _, self.suffix_format_map = config_ini(prompt_texconv_path=False, profile_name=profile_name)
            self.load_profiles()
            self.profile_dropdown.setCurrentText(profile_name)
            self.save_config()
            self.log.append(f"Added new profile: {profile_name}")

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
            ini_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Universal-DDS-Exporter-PluginSettings.ini")
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
                self.log.append(f"Deleted profile: {profile_name}")

    # Toggle the wiki visibility
    def toggle_wiki(self):
        if self.wiki_area.isVisible():
            self.wiki_area.hide()
            self.button_show_wiki.setText("Show Wiki")
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
            self.TexConvPath = new_path
            self.save_config()
            self.log_signal.emit(f"Updated TexConv Path: {self.TexConvPath}")
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
        else:
            self.log.show()
            self.button_display_log.setText("Hide Log")

    # Handle export DDS files checkbox change
    def checkbox_export_change(self, state):
        self.export = self.checkbox.isChecked()  # Corrected: Use isChecked()
        self.save_config()
        self.log_signal.emit(f"Export DDS Files set to: {self.export}")

    # Handle overwrite DDS files checkbox change
    def checkbox_overwrite_change(self, state):
        self.overwrite = self.checkbox_overwrite.isChecked()  # Corrected: Use isChecked()
        self.save_config()
        self.log_signal.emit(f"Overwrite DDS Files set to: {self.overwrite}")

    # Save the current plugin configuration to the ini file
    def save_config(self):
        ini_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Universal-DDS-Exporter-PluginSettings.ini")
        config = configparser.ConfigParser()
        config.optionxform = str  # Preserve case of options

        config.read(ini_file_path)

        # Save global settings
        config['General']['TexConvDirectory'] = self.TexConvPath
        config['General']['ExportDDSFiles'] = str(self.export)
        config['General']['OverwriteDDSFiles'] = str(self.overwrite)

        # Save suffix formats for the current profile
        profile_name = self.profile_dropdown.currentText()
        suffix_section = f"{profile_name}_SuffixFormats"
        
        if suffix_section not in config:
            config[suffix_section] = {}
        
        # Clear existing suffix formats for the profile
        config.remove_section(suffix_section)
        config.add_section(suffix_section)
        
        for suffix, format_option in self.suffix_format_map.items():
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
        for suffix, format_option in self.suffix_format_map.items():
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
            self.button_texconv.clicked.disconnect(self.button_texconv_clicked)
            self.button_clear.clicked.disconnect(self.button_clear_clicked)
            self.button_display_log.clicked.disconnect(self.toggle_log_display)
            self.button_export_textures.clicked.disconnect(self.open_export_textures_window)
            self.button_show_wiki.clicked.disconnect(self.toggle_wiki)
            self.button_add.clicked.disconnect(self.add_suffix_format_row)
            self.button_remove.clicked.disconnect(self.remove_last_suffix_format_row)
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
        if not self.export:
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
                if file_path.endswith(".png"):
                    result_message = convert_png_to_dds(self.TexConvPath, file_path, self.overwrite, suffix_format_map)
                    if result_message:
                        self.log_signal.emit(f"  {result_message}")

    # Helper function to get the suffix format map from the UI
    def get_suffix_format_map(self):
        return self.suffix_format_map.copy()

    # Handle export error event
    def on_export_error(self, err):
        self.log_signal.emit("Export failed.")
        self.log_signal.emit(repr(err))

# Global plugin instance
Universal_DDS_PLUGIN = None

# Function called when the plugin is started
def start_plugin():
    """This method is called when the plugin is started.""" 
    logger.info("Universal DDS Exporter Plugin Initialized")
    global Universal_DDS_PLUGIN
    Universal_DDS_PLUGIN = UniversalDDSPlugin()

# Function called when the plugin is closed
def close_plugin():
    """This method is called when the plugin is stopped.""" 
    logger.info("Universal DDS Exporter Plugin Shutdown")
    global Universal_DDS_PLUGIN
    if Universal_DDS_PLUGIN:
        Universal_DDS_PLUGIN.cleanup()
        Universal_DDS_PLUGIN = None

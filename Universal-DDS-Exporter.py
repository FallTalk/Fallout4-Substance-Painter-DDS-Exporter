__author__ = "Emil Eldstål"
__copyright__ = "Copyright 2023, Emil Eldstål"
__version__ = "0.1.1"
__forkedVersion__ = "1.0.2"
__painterVersion__ = "10.1.0"

# Qt5 vs Qt6 check import
# Painter version 10.1 moved from Qt5 to Qt6, which introduces breaking changes in Python plugins. The most notable change in the PySide module going from version 2 to 6.
import substance_painter as sp
IsQt5 = sp.application.version_info() < (10,1,0)

if IsQt5 :
    from PySide2 import QtWidgets
    from PySide2.QtCore import Qt
    from PySide2.QtGui import QKeyEvent
else :
    from PySide6 import QtWidgets
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent

import substance_painter.ui
import substance_painter.event

import os
import configparser
import subprocess

# Function to load and update settings from the ini configuration file
def config_ini(overwrite):
    # Get the path to the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define the path to the UniversalPluginSettings.ini file
    ini_file_path = os.path.join(script_dir, "Universal-DDS-Exporter-PluginSettings.ini")
    
    # Create a ConfigParser object
    config = configparser.ConfigParser()
    config.optionxform = str  # Preserve case of options

    # Check if the INI file exists
    if os.path.exists(ini_file_path):
        # Read the INI file
        config.read(ini_file_path)
        
        # Check if the section and key exist
        if 'General' in config:
            # Set TexConv path if not already set, or if overwriting is required
            if 'TexConvDirectory' not in config['General'] or not config['General']['TexConvDirectory']:
                # Let's the user choose where TexConv is if not configured
                config['General']['TexConvDirectory'] = choose_texconv_folder()
            if overwrite:
                # Let's the user choose where TexConv is if using overwrite button
                config['General']['TexConvDirectory'] = choose_texconv_folder()

            # Assign the TexConvDirectory value to the TexConvPath variable
            TexConvPath = config['General']['TexConvDirectory']
            export_state = config.getboolean('General', 'ExportDDSFiles', fallback=False)
            overwrite_state = config.getboolean('General', 'OverwriteDDSFiles', fallback=False)
            suffix_format_map = dict(config.items('SuffixFormats')) if 'SuffixFormats' in config else {}
        else:
            # Default settings if no General section exists in the ini
            TexConvPath = choose_texconv_folder()
            config['General'] = {
                'TexConvDirectory': TexConvPath,
                'ExportDDSFiles': 'False',
                'OverwriteDDSFiles': 'False'
            }
            export_state = False
            overwrite_state = False
            suffix_format_map = {}
            print("Universal DDS Exporter Plugin: TexConvDirectory value set or updated in UniversalPluginSettings.ini")

        # Write the updated configuration back to the INI file
        with open(ini_file_path, 'w') as configfile:
            config.write(configfile)
    else:
        # If the INI file doesn't exist, create it and set the value
        TexConvPath = choose_texconv_folder()
        with open(ini_file_path, 'w') as configfile:
            config['General'] = {
                'TexConvDirectory': TexConvPath,
                'ExportDDSFiles': 'False',
                'OverwriteDDSFiles': 'False'
            }
            config.write(configfile)
        export_state = False
        overwrite_state = False
        suffix_format_map = {}

    return TexConvPath, export_state, overwrite_state, suffix_format_map

# Opens a dialog to choose the TexConv folder location
def choose_texconv_folder():
    path = QtWidgets.QFileDialog.getExistingDirectory(
        substance_painter.ui.get_main_window(), "Choose Texconv directory")
    return path + "/texconv.exe"

# Function to convert PNG files to DDS format using TexConv
def convert_png_to_dds(texconvPath, sourcePNG, overwrite, suffix_format_map):
    # Replace backslashes with forward slashes in the provided paths
    texconvPath = texconvPath.replace('\\', '/')
    sourceFolder = os.path.dirname(sourcePNG).replace('\\', '/')
    outputFolder = os.path.join(sourceFolder, "DDS").replace('\\', '/')
    outputFile = os.path.join(outputFolder, os.path.splitext(os.path.basename(sourcePNG))[0] + ".dds").replace('\\', '/')

    # Ensure DDS subfolder exists
    if not os.path.exists(outputFolder):
        # Create the DDS directory if it does not exist
        os.makedirs(outputFolder)
        print("Created DDS subfolder")

    # for filename in os.listdir(sourceFolder):
    filename = os.path.basename(sourcePNG)
    if filename.endswith(".png"):
        sourceFile = os.path.splitext(filename)[0]

        # Extract suffix and choose corresponding DDS format from suffix_format_map
        if '_' in sourceFile:
            suffix = sourceFile.rsplit('_', 1)[-1].rstrip('_')
            format_option = suffix_format_map.get(suffix, "BC7_UNORM")
        else:
            # If no suffix defined
            suffix = None
            format_option = "BC7_UNORM"

        print(f"Processing {filename}")
        print(f"Extracted suffix: {suffix}")
        print(f"Chosen format: {format_option}")

        # Set overwrite_option based on the state
        overwrite_option = "-y" if overwrite else ""

        # Check if DDS file already exists and if overwrite is disabled
        if overwrite or not os.path.exists(outputFile):
            texconv_cmd = [
                texconvPath,
                "-nologo",
                overwrite_option,
                "-o", outputFolder,
                "-f", format_option,
                os.path.join(sourceFolder, filename)
            ]

            texconv_cmd_str = subprocess.list2cmdline(texconv_cmd)
            print(f"Running command: {texconv_cmd_str}")

            # Run TexConv command
            try:
                subprocess.run(texconv_cmd_str, shell=True, check=True)
                print(f"Successfully converted {filename} to {outputFile} using {format_option}")
                return f"Converted {filename} to {outputFile} with format {format_option}"
            except subprocess.CalledProcessError as e:
                print(f"Failed to convert {filename}: {e}")
                return f"Failed to convert {filename}"
        else:
            print(f"Skipping conversion for {filename}, DDS file already exists and overwrite is disabled.")
            return f"Skipping conversion for {filename}, DDS file already exists."

    return ""

# Main plugin class
class UniversalDDSPlugin:
    def __init__(self):
        # Load configuration and initialize UI components
        self.TexConvPath, self.export, self.overwrite, self.suffix_format_map = config_ini(False)
        self.version = "1.0.0"

        # Create log area
        self.log = QtWidgets.QTextEdit()
        self.log.setReadOnly(True)
        
        # Main window and layout initialization
        self.window = QtWidgets.QWidget()

        main_layout = QtWidgets.QVBoxLayout()
        top_row_layout = QtWidgets.QHBoxLayout()
        suffix_format_scroll_area = QtWidgets.QScrollArea()
        suffix_format_widget = QtWidgets.QWidget()
        self.suffix_format_layout = QtWidgets.QVBoxLayout(suffix_format_widget)
        
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
        version_label = QtWidgets.QLabel("Version: {}".format(self.version))
        
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

        # Load suffix formats from config
        self.load_suffix_formats()
        suffix_format_scroll_area.setWidget(suffix_format_widget)
        suffix_format_scroll_area.setWidgetResizable(True)
        suffix_format_scroll_area.setMinimumWidth(300)

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

        # Add the window to the Substance Painter UI
        substance_painter.ui.add_dock_widget(self.window)
        self.log.append("TexConv Path: {}".format(self.TexConvPath))

        # Connect export event handler
        connections = {
            substance_painter.event.ExportTexturesEnded: self.on_export_finished
        }
        for event, callback in connections.items():
            substance_painter.event.DISPATCHER.connect(event, callback)
            
    # Toggle the wiki visibility
    def toggle_wiki(self):
        if self.wiki_area.isVisible():
            self.wiki_area.hide()
            self.button_show_wiki.setText("Show wiki")
        else:
            # Load the text from a .txt file
            wiki_file_path = os.path.join(os.path.dirname(__file__), "wiki.txt")
            if os.path.exists(wiki_file_path):
                with open(wiki_file_path, 'r') as wiki_file:
                    self.wiki_area.setPlainText(wiki_file.read())

            self.wiki_area.show()
            self.button_show_wiki.setText("Hide wiki")

    # Function to simulate Ctrl+Shift+E to open the export window
    def open_export_textures_window(self):
        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_E, Qt.ControlModifier | Qt.ShiftModifier)
        QtWidgets.QApplication.sendEvent(substance_painter.ui.get_main_window(), event)

    # Add a new suffix format row to the UI
    def add_suffix_format_row(self):
        row_layout = QtWidgets.QHBoxLayout()

        # Create the suffix input and format dropdown
        suffix_input = QtWidgets.QLineEdit()
        suffix_input.setPlaceholderText("Suffix")
        format_dropdown = QtWidgets.QComboBox()
        format_dropdown.addItems([
            "BC1_UNORM",
            "BC2_UNORM",
            "BC3_UNORM",
            "BC4_UNORM",
            "BC5_UNORM",
            "BC6H_UF16",
            "BC7_UNORM",
            "R8G8B8A8_UNORM",
            "R16G16B16A16_UNORM", "R16G16B16A16_FLOAT",
            "R32G32B32A32_FLOAT"
        ])

        # Add the widgets to the row
        row_layout.addWidget(suffix_input)
        row_layout.addWidget(format_dropdown)
        self.suffix_format_layout.addLayout(row_layout)

        # Store suffix and format in the config when edited
        def capture_and_store_suffix_format():
            suffix = suffix_input.text()
            selected_format = format_dropdown.currentText()

            # Prevent duplicate suffixes
            if suffix in self.suffix_format_map and suffix_input.isEnabled():
                error_dialog = QtWidgets.QMessageBox()
                error_dialog.setIcon(QtWidgets.QMessageBox.Warning)
                error_dialog.setWindowTitle("Duplicate Suffix")
                error_dialog.setText(f"The suffix '{suffix}' already exists. Please use a unique suffix.")
                error_dialog.setStandardButtons(QtWidgets.QMessageBox.Ok)
                error_dialog.exec_()
                return

            if suffix:
                # Add the suffix and format to the suffix_format_map
                self.suffix_format_map[suffix] = selected_format

                # Update the .ini file
                script_dir = os.path.dirname(os.path.abspath(__file__))
                ini_file_path = os.path.join(script_dir, "Universal-DDS-Exporter-PluginSettings.ini")
                config = configparser.ConfigParser()

                # Preserve case sensitivity for the suffixes
                config.optionxform = str
                config.read(ini_file_path)

                # Ensure the 'SuffixFormats' section exists
                if 'SuffixFormats' not in config:
                    config['SuffixFormats'] = {}

                # Add/Update the suffix and format in the .ini file
                config['SuffixFormats'][suffix] = selected_format

                # Write the updated suffix_format_map to the .ini file
                with open(ini_file_path, 'w') as configfile:
                    config.write(configfile)

                print(f"Added suffix {suffix} with format {selected_format} to the .ini file.")

        # Connect the editing finished signal to capture the suffix when input is complete
        suffix_input.editingFinished.connect(capture_and_store_suffix_format)

        # Update format in the .ini file whenever a new format is selected
        def update_format_on_change():
            suffix = suffix_input.text()
            selected_format = format_dropdown.currentText()

            if suffix in self.suffix_format_map:
                # Update the format in suffix_format_map
                self.suffix_format_map[suffix] = selected_format

                # Update the .ini file
                script_dir = os.path.dirname(os.path.abspath(__file__))
                ini_file_path = os.path.join(script_dir, "Universal-DDS-Exporter-PluginSettings.ini")
                config = configparser.ConfigParser()
                config.optionxform = str
                config.read(ini_file_path)

                # Update the format for the existing suffix in the .ini file
                config['SuffixFormats'][suffix] = selected_format

                # Write the changes to the .ini file
                with open(ini_file_path, 'w') as configfile:
                    config.write(configfile)

                print(f"Updated format for suffix {suffix} to {selected_format} in the .ini file.")

        # Connect the currentIndexChanged signal of the dropdown to update the format when changed
        format_dropdown.currentIndexChanged.connect(update_format_on_change)

    # Remove the last added suffix format row
    def remove_last_suffix_format_row(self):
        if self.suffix_format_layout.count() > 1:
            last_item = self.suffix_format_layout.itemAt(self.suffix_format_layout.count() - 1)
            if last_item:
                layout = last_item.layout()
                if layout:
                    for i in range(layout.count()):
                        widget = layout.itemAt(i).widget()
                        if widget:
                            widget.deleteLater()
                    self.suffix_format_layout.removeItem(last_item)
                else:
                    self.suffix_format_layout.removeItem(last_item)

    # Handle TexConv location button click
    def button_texconv_clicked(self):
        self.TexConvPath, _, _, _ = config_ini(True)
        self.log.append("New TexConv Path: {}".format(self.TexConvPath))

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
        self.export = state == Qt.Checked.value
        self.save_config()

    # Handle overwrite DDS files checkbox change
    def checkbox_overwrite_change(self, state):
        self.overwrite = state == Qt.Checked.value
        self.save_config()

    # Save the current plugin configuration to the ini file
    def save_config(self):
        ini_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Universal-DDS-Exporter-PluginSettings.ini")
        config = configparser.ConfigParser()
        config.optionxform = str  # Preserve case of options

        if os.path.exists(ini_file_path):
            config.read(ini_file_path)
        else:
            config['General'] = {}

        # Save export and overwrite settings
        config['General']['ExportDDSFiles'] = str(self.export)
        config['General']['OverwriteDDSFiles'] = str(self.overwrite)

        # Save suffix formats
        if 'SuffixFormats' not in config:
            config.add_section('SuffixFormats')

        for i in range(self.suffix_format_layout.count()):
            row_layout = self.suffix_format_layout.itemAt(i)
            if row_layout:
                suffix_input = row_layout.itemAt(0).widget()
                format_dropdown = row_layout.itemAt(1).widget()
                if suffix_input and format_dropdown:
                    suffix = suffix_input.text().strip()
                    format_option = format_dropdown.currentText()
                    if suffix:
                        config['SuffixFormats'][suffix] = format_option

        # Write updated config to the ini file
        with open(ini_file_path, 'w') as configfile:
            config.write(configfile)

    # Load suffix formats from the ini file into the UI
    def load_suffix_formats(self):
        for suffix, format_option in self.suffix_format_map.items():
            self.add_suffix_format_row()
            row_layout = self.suffix_format_layout.itemAt(self.suffix_format_layout.count() - 1)
            suffix_input = row_layout.itemAt(0).widget()
            format_dropdown = row_layout.itemAt(1).widget()
            if suffix_input and format_dropdown:
                suffix_input.setText(suffix)
                index = format_dropdown.findText(format_option)
                if index != -1:
                    format_dropdown.setCurrentIndex(index)

    # Cleanup function when the plugin is unloaded
    def __del__(self):
        substance_painter.ui.delete_ui_element(self.log)
        substance_painter.ui.delete_ui_element(self.window)

    # Handle export finished event from Substance Painter
    def on_export_finished(self, res):
        if not self.export:
            self.log.append("DDS export is disabled. No files will be processed.")
            return
        
        self.log.append(res.message)
        self.log.append("Exported files:")

        for file_list in res.textures.values():
            for file_path in file_list:
                self.log.append("  {}".format(file_path))

        self.log.append("Converting to DDS files:")

        suffix_format_map = self.get_suffix_format_map()

        for file_list in res.textures.values():
            for file_path in file_list:
                if file_path.endswith(".png"):
                    result_message = convert_png_to_dds(self.TexConvPath, file_path, self.overwrite, suffix_format_map)
                    self.log.append(f"  {result_message}")

    # Helper function to get the suffix format map from the UI
    def get_suffix_format_map(self):
        suffix_format_map = {}
        for i in range(self.suffix_format_layout.count()):
            row_layout = self.suffix_format_layout.itemAt(i)
            if row_layout:
                suffix_input = row_layout.itemAt(0).widget()
                format_dropdown = row_layout.itemAt(1).widget()
                if suffix_input and format_dropdown:
                    suffix = suffix_input.text().strip()
                    format_option = format_dropdown.currentText()
                    if suffix:
                        suffix_format_map[suffix] = format_option
        return suffix_format_map

    # Handle export error event
    def on_export_error(self, err):
        self.log.append("Export failed.")
        self.log.append(repr(err))

Universal_DDS_PLUGIN = None

# Function called when the plugin is started
def start_plugin():
    """This method is called when the plugin is started.""" 
    print("Universal DDS Exporter Plugin Initialized")
    global Universal_DDS_PLUGIN
    Universal_DDS_PLUGIN = UniversalDDSPlugin()

# Function called when the plugin is closed
def close_plugin():
    """This method is called when the plugin is stopped.""" 
    print("Universal DDS Exporter Plugin Shutdown")
    global Universal_DDS_PLUGIN
    del Universal_DDS_PLUGIN

if __name__ == "__main__":
    start_plugin()

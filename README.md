<h1 align="center">
Universal Substance Painter DDS Exporter
</h1>

![banner](https://staticdelivery.nexusmods.com/mods/2295/images/1044/1044-1726769824-1173798291.png)

# Mod Page

https://www.nexusmods.com/site/mods/1044


**Description:**
A Substance Painter DDS export plugin to automate the PNG to DDS conversion.
No more spending minutes converting those 20 different maps to DDS via PS/Intel/Paint.net etc

Export textures as normal with the Universal export selected and the checkboxes ticked.
It will create a DDS subfolder of where you exported the .PNG textures.
Textures will be converted to DDS based on your defined suffixes and dds options.

You might have to delete the DDS files if you want to re-export as it might not overwrite the files.


**Changes made:**

* State of checkboxes is now stored in the ini config files so it will remember your selection.
* Added a Show/Hide log button
* Added a "Export Textures" button so you no longer have to drag the mouse to the top left and select File => Export textures or press Ctrl+Shift+E.
* Added a built-in wiki which will display info regarding the available dds options and some other info, it also has a Show/Hide button.
* Instead of the suffixes and dds options being defined in the py script, these are now defined by you, the user, simply click the add button each time you want to define a new suffix and a dds option for that suffix and define them in the input and dropdown menu. There is also a remove button to remove the last added suffix, it also has safety checks to prevent duplicate suffixes and such.
* User defined suffixes are stored in the ini config file so you won't have to re-define them everytime.

# Installation:


Retrieve the files from the forked GitHub Repo linked below.
Extract the universal-dds-exporter.py into your Substance Painter Plugin folder:
C:\Users\username\Documents\Adobe\Adobe Substance 3D Painter\python\plugins
(Can also be found using the Python > Plugins Folder button in the top row)

**Export preset:**
Move the .spexp from the optional files to this folder:
C:\Users\username\Documents\Adobe\Adobe Substance 3D Painter\assets\export-presets
I have provided an example export preset in the files section but you are free to use any export template or your own preset(s).

**Wiki:**
Move the wiki.txt from the optional files to this folder:
C:\Users\username\Documents\Adobe\Adobe Substance 3D Painter\python\plugins

Enable the Universal-DDS-Exporter under the Python menu
First time running the plugin it will ask you what folder the Texconv.exe is located in via a UI pop-up.
This will create a Universal-DDS-Exporter-PluginSettings.ini in the plugin folder with the settings saved.

## Enable the Universal-DDS-Exporter under the Python menu

First time running the plugin it will ask you what folder the Texconv.exe is located in via a UI pop-up. This will create a Universal-DDS-Exporter-PluginSettings.ini in the plugin folder with the settings saved.

![plugin widget](https://staticdelivery.nexusmods.com/mods/4187/images/4891/4891-1696725603-1907132508.png)
Dockable widget with output terminal and basic settings

# Dependencies:

Microsoft Texconv (Download and extract to whatever folder you want)

https://github.com/Microsoft/DirectXTex/wiki/Texconv

# Compatibility

Developed and tested with Substance Painter 10.0.1 (2024)

## Support

For support, please use this repository's GitHub Issues tracking service. Feel free to send me an email if you use and like the plugin.

Copyright (c) 2023 Emil Eldstål

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

* Instead of the suffixes and dds options being defined in the py script, these are now defined by you, the user, simply click the add button each time you want to define a new suffix and a dds option for that suffix and define them in the input and dropdown menu.
  
* Profiling system so you can have dedicated suffix-formats for different games or projects.

* DDS Options available are: BC1_UNORM, BC1_UNORM_SRGB, BC1_ALPHA_UNORM, BC1_ALPHA_UNORM_SRGB, BC2_UNORM, BC2_UNORM_SRGB, BC3_UNORM, BC3_UNORM_SRGB, BC4_UNORM, BC4_SNORM, BC5_UNORM, BC5_SNORM, BC6H_UF16, BC6H_SF16, BC7_UNORM, BC7_UNORM_SRGB, R32G32B32A32_FLOAT, R32G32B32_FLOAT, R16G16B16A16_FLOAT, R16G16B16A16_UNORM, R16G16B16A16_SNORM, R32G32_FLOAT, R10G10B10A2_UNORM, R11G11B10_FLOAT, R8G8B8A8_UNORM, R8G8B8A8_UNORM_SRGB, R8G8B8A8_SNORM, R16G16_FLOAT, R16G16_UNORM, R16G16_SNORM, R32_FLOAT, R8G8_UNORM, R8G8_SNORM, R16_FLOAT, R16_UNORM, R16_SNORM, R8_UNORM, R8_SNORM, A8_UNORM, R8G8_B8G8_UNORM, G8R8_G8B8_UNORM, B5G6R5_UNORM, B5G5R5A1_UNORM, B8G8R8A8_UNORM, B8G8R8X8_UNORM, B8G8R8A8_UNORM_SRGB, B8G8R8X8_UNORM_SRGB, B4G4R4A4_UNORM, A4B4G4R4_UNORM, BC3n.

* Remove button to remove the last added suffix + safety checks to prevent duplicate suffixes and such.

* User defined suffixes, state of checkboxes are now stored in the ini config files so your selections, defined suffixes and dds options will be remembered.

* Added a Show/Hide log button.

* Added a "Export Textures" button so you no longer have to drag the mouse to the top left and select File => Export textures or press Ctrl+Shift+E.

* Added a built-in wiki which will display info regarding the available dds options and some other info, it also has a Show/Hide button.

* By default, texture channels in your templates which do not have a suffix and a dds option defined in this DDS exporter will be converted to BC7_UNORM.

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

<img width="578" height="445" alt="Screenshot 2025-09-05 082551" src="https://github.com/user-attachments/assets/cdad2c6c-62dc-4505-b656-46bf10192d8a" />

Dockable widget with output terminal and basic settings

# Dependencies:

Microsoft Texconv (Download and extract to whatever folder you want)

https://github.com/Microsoft/DirectXTex/wiki/Texconv

# Compatibility

Developed and tested with Substance Painter 10.0.1 (2024)

## Support

For support, please use this repository's GitHub Issues tracking service. Feel free to send me an email if you use and like the plugin.

Copyright (c) 2023 Emil Eldstål

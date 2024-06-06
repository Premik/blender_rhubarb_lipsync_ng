# Basic troubleshoting guide

## Determine at which stage the problem occures

<details>
  <summary> <b>Was addon installed ?</b> </summary>


After the addon was installed from the `zip` file it should show up in the preferences:

- Go to `Main menu/Edit/Preferences/Add-ons`
- Search addond by name. Type `rh` into the search box

If you can see `Animations: Rhubarb Lipsync NG` item the plugin has been installed sucessfully and you can proceed to the next section.

![Check installed](doc/img/checkPuginInstalled.png)

If the installation failed:
- Make sure the Blender version is compatible with the addon version. Each Blender version comes with it's own Python version.
- The addon `zip-file` used for the installation was incorrect. Make soure you have downloaded the correct zip file (and not for instance sources snapshot). Don't unzip the file. Ensure the file is not corrupted because of download error.
- Try to [fully reinstall the addon](#reinstalling-the-addon).
- Try to [collect debug messages](#reinstalling-the-addon) to find the root cause or any additional details.
- Search [existing tickets](https://github.com/Premik/blender_rhubarb_lipsync_ng/issues?q=), including the closed ones. Maybe somebody had similar issue before.
- Report the [bug](https://github.com/Premik/blender_rhubarb_lipsync_ng/issues/new/choose)

---

</details>

<details>
  <summary> <b>Was addon registered ?</b> </summary>

After addon is installed it should get registered. This happends after the addon is enabled in the preferences:

- Again go to the `Main menu/Edit/Preferences/Add-ons`
- Search addond by name. Type `rh` into the search box
- Check the checkbox in front of addon name.

If no errors should get shown and you see the addon preferences below the addon details, then the addon has been registered/enabled sucessfully. Proceed to the next section.

![Check installed](doc/img/checkPluginRegistered.png)

When addon fails to install or register Blender often shows a popup with Python error and stacktrace. Unfortunately very often this error is a generic one with no useful details. For example:

Where the actual useful error details ( root cause) was printed earlier to the system console.

---

</details>

## Reinstalling the addon

Sometimes Blender fails to properly remove the addon files when the plugin is uninstalled. This happens more likely when there were some issues with addon installation/registration earlier.

First try the straighforward approach:

- Disable the addon by unchecking the addon in the preferences.
- Click `Remove` botton to make Blender delete the addon.
- Restart Blender by closing and reopening it.

Now you can install the addon again. If still no luck try to remote the addon manually:

- First make sure the addon is removed and doesn't show up in the preferences.
- Navigate to the [Blender's user folder](https://docs.blender.org/manual/en/latest/advanced/blender_directory_layout.html) inside your home folder. And then to the `scripts/addons` subfolder.
- Inspect the `addons` folder content. If you could see any `rhubarb_lipsync` folder or files there **remove the it** completly.
- You can also easily find the path at the addon preferences page in the `File:` label:

![Check installed](doc/img/addonPath.png)

### Collecting debug messages

Start Blender with `--debug`` flag. This will make the addon to log additional information to console at the very early stage of registration. This might contain crucial clues about why the issue is happening or at least help narrowing it down. 

```sh
> blender --debug
Switching to fully guarded memory allocator.
Blender 3.5.1
Build: 2023-04-24 23:56:35 Windows release
argv[0] = C:\Program Files\Blender Foundation\Blender 3.5\blender.exe
argv[1] = --debug
Read prefs: C:\users\premik\AppData\Roaming\Blender Foundation\Blender\3.5\config\userpref.blend
Read prefs: r:/blenderFreshWin\config\userpref.blend
```
Note there might be some additional log lines. For example messages from other plugins.

```sh
addon_utils.disable: rhubarb_lipsync not disabled
Modules Installed (rhubarb_lipsync) from 'C:\dist\rhubarb_lipsync_ng-Windows-1.3.1.zip' into 'C:\users\premik\AppData\Roaming\Blender Foundation\Blender\3.5\scripts\addons'
```

```sh
RLPS: enter register()
RLPS: enter init_loggers()
Added console handler on 15 loggers.
RLPS Set TRACE level for 16 loggers
Added console handler on 0 loggers.
RLPS: exit register()
Warning: This script was written Blender version 4.0.2 and might not function (correctly), though it is enabled
```

- Start Blender from she'll (Linux Mac) to see the console messaged. On Windows open the console from system menu.
- if you see the addon listed, try to remove it complete and install.
- in some rare circumstances There could be some inference with other add-ons or something specific to Blender customization. To rule this possibilty out start Blender with Factor settings. This can be done by settings some environment variables to a temporary folder. There is also a script for power users which does this automatically (including downloading and registering the addon into this sandbox
- note the addon has several automated unit tests and integration tests. Those run the basic addon operators in a headless blender (blender as module). Tests are ran automatically after each change on GitHub for all three supported platforms.
- check the GitHub issues, including the closed tickets. Maybe so



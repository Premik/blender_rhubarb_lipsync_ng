# Basic addon troubleshoting guide

## Determine at which stage the problem occures

<details>
  <summary> <b>Was the addon installed sucessfully ?</b> </summary>


When the addon was installed from the `zip` file it should show up in the preferences:

- Go to `Main menu/Edit/Preferences/Add-ons`
- Search addond by name. Type `rh` into the search box

If you can see `Animations: Rhubarb Lipsync NG` item the plugin has been installed sucessfully and you can proceed to the next section.

![Check installed](doc/img/checkPuginInstalled.png)

If the installation failed:
- Make sure the Blender version is compatible with the addon version. Each Blender version comes with it's own Python version on older version might not work.
- The addon `zip-file` used for the installation was incorrect. Make soure you have downloaded the correct zip file (and not for instance sources snapshot). Don't unzip the file. Ensure the file is not corrupted because of download error.
- There could be some problem access the `addons` folder. Like permission issues.


- Try to [fully reinstall the addon](#reinstalling-the-addon).
- Try to [collect debug messages](#collecting-debug-messages-for-console) to find the root cause or any additional details.
- Search [existing tickets](https://github.com/Premik/blender_rhubarb_lipsync_ng/issues?q=), including the closed ones. Maybe somebody had similar issue before.
- Report the [bug](https://github.com/Premik/blender_rhubarb_lipsync_ng/issues/new/choose)

---

</details>

<details>
  <summary> <b>Was the addon enabled/registered sucessfully ?</b> </summary>

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

## Enable verbose log messages

Collecting log messages before an issue happens if very useful for further troubleshooting. There are two options how to enable verbose logging.

1. [Start Blender with debug flag from shell/console](#collecting-debug-messages-for-console). This is the only option if the plugin won't install/register.
1. Set the log verbosity and log file in the addon preferences:



## Reinstalling the addon

Sometimes where there is an unexpected error the addon classes might still be registered in memory even thought the addon is disabled/removed. Until Blender is restarted. So first try the following steps:

- Disable the addon by unchecking the addon in the preferences.
- Click `Remove` botton to make Blender delete the addon.
- Restart Blender by closing and reopening it.
- Install and enable the addon again.


If still no luck try to ensure there are no files left over the addon was removed. 
Sometimes Blender fails to properly remove the addon files when the plugin is uninstalled. For example when some file is locked by os or because of a bug. Then the addon could be in a strange state where it won't show up in the addons list but there still might be some files on the disk.

To recover, try to following steps:
- First make sure the addon is removed and doesn't show up in the addon list in the preferences.
- Stop Blender.
- Navigate to the [Blender's user folder](https://docs.blender.org/manual/en/latest/advanced/blender_directory_layout.html) inside your home folder. And then to the `scripts/addons` subfolder.
- Inspect the `addons` folder content. If you could see any `rhubarb_lipsync` folder or files there **remove it** completly.
- You can also easily find the path at the addon preferences page in the `File:` label:

![Check installed](doc/img/addonPath.png)

- Start Blender
- Install and enable the addon again.

If still not luck follow the next section and run Blender with a fresh profile.

## Run Blender with fresh profile (factory settings)

In some rare circumstances there could be some inference with other add-ons or something Blender customization which might be causing troubles. To rule this possibilty out start Blender with Factor settings. This can be done by settings some environment variables to a temporary folder so your original profile can be left intact.

On windows:

```sh
set BLENDER_USER_RESOURCES=%TEMP%
blender --debug
```

On linux/mac:

```sh
XDG_CONFIG_HOME="/tmp/blenderFresh" blender --debug
```

Then install the plugin as the usuall way.


## Collecting debug messages for console

Start Blender with `--debug` flag. This will make the addon to log additional information to console at the very early stage of registration. This might contain crucial clues about why the issue is happening or at least help narrowing it down. You can also add `--debug-python` to get even more details related to addon registration and python in general.

```sh
> blender --debug
Switching to fully guarded memory allocator.
Blender 3.5.1
Build: 2023-04-24 23:56:35 Windows release
argv[0] = C:\Program Files\Blender Foundation\Blender 3.5\blender.exe
argv[1] = --debug
Read prefs: C:\users\premik\AppData\Roaming\Blender Foundation\Blender\3.5\config\userpref.blend
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

```
Traceback (most recent call last):
  File "/usr/share/blender/4.2/scripts/startup/bl_operators/userpref.py", line 692, in execute
    _module_filesystem_remove(path_addons, f)
  File "/usr/share/blender/4.2/scripts/startup/bl_operators/userpref.py", line 52, in _module_filesystem_remove
    shutil.rmtree(f_full)
  File "/usr/lib/python3.11/shutil.py", line 744, in rmtree
    onerror(os.path.islink, path, sys.exc_info())
  File "/usr/lib/python3.11/shutil.py", line 742, in rmtree
    raise OSError("Cannot call rmtree on a symbolic link")
OSError: Cannot call rmtree on a symbolic link
```

- Search [Opened issues](https://github.com/Premik/blender_rhubarb_lipsync_ng/issues?q=is%3Aopen). Maybe somebody has already reported the same issue.
- Also search already [Closed issues](https://github.com/Premik/blender_rhubarb_lipsync_ng/issues?q=is%3Aclosed). There might be similar issue with a solution from the past.

- The addon has several automated unit tests and integration tests. Those verifies the basic addon operators in a headless Blender (Blender as module) environment. Tests are ran automatically after each change on GitHub for all three supported platforms. You can see them on the [Github Actions](https://github.com/Premik/blender_rhubarb_lipsync_ng/actions/workflows/unit-tests.yml). There shouldn't be any tests failing.

![Check installed](doc/img/GithubActions.png)


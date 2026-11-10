# Basic Addon Troubleshooting Guide

## Determine at Which Stage the Problem Occurs

<details>
  <summary> <b>Was the addon installed successfully?</b> </summary>


When the addon is installed from the `zip` file, it should show up in the preferences:

- Go to `Main menu/Edit/Preferences/Add-ons`
- Search for the addon by name. Type `rh` into the search box

If you can see the Animations: Rhubarb Lipsync NG item, the plugin has been installed successfully, and you can proceed to the next section.

![Check installed](doc/img/checkPuginInstalled.png)

If the installation failed:
- Ensure the Blender version is compatible with the addon version. Each Blender version comes with its own Python version, and older versions might not work.

- Verify the addon `zip-file` used for the installation is correct. Make sure you have downloaded the correct zip file (and not, for instance, a source snapshot). Don't unzip the file. Ensure the file is not corrupted due to a download error.
There could be problems accessing the `addons` folder, such as permission issues.


- Try to [fully reinstall the addon](#reinstalling-the-addon).
- Try to [collect debug messages](#collecting-debug-messages-for-console) to find the root cause or any additional details.
- Search [existing tickets](https://github.com/Premik/blender_rhubarb_lipsync_ng/issues?q=), including the closed ones. Maybe somebody had similar issue before.
- Report the [bug](https://github.com/Premik/blender_rhubarb_lipsync_ng/issues/new/choose)

---

</details>

<details>
  <summary> <b>Was the addon enabled/registered successfully?</b> </summary>

After the addon is installed, it should get registered. This happens after the addon is enabled in the preferences:

- Again, go to `Main menu/Edit/Preferences/Add-ons`
- Search for the addon by name. Type `rh` into the search box
- Check the checkbox in front of the addon name.

If no errors are shown and you see the addon preferences below the addon details, then the addon has been registered/enabled successfully. Proceed to the next section.

![Check installed](doc/img/checkPluginRegistered.png)

When the addon fails to install or register, Blender often shows a popup with a Python error and stack trace. Unfortunately, this error is often generic and not useful. For example:

```
AttributeError: partially initialized module 'rhubarb_lipsync' has no attribute 'blender' (most likely due to a circular import)
```

The actual useful error details (root cause) might have been printed earlier to the system console.

---

</details>

## Enable Verbose Log Messages

Collecting log messages before an issue happens is very useful for further troubleshooting. There are two options for enabling verbose logging:

1. [Start Blender with the debug flag from shell/console](#collecting-debug-messages-for-console). This is the only option if the plugin won't install/register.
1. Set the log verbosity and log file in the addon preferences:
   - Go to `Main menu/Edit/Preferences/Add-ons`, search for `rh`, and expand the addon preferences.
   - Set `Log level` to `TRACE` (or `DEBUG`) to get detailed messages. Optionally set a `Log File` path to also write the messages to a file.
   - File logging is set up while the addon registers. Errors that occur before file logging is successfully set up—including import-time and early registration failures—only appear in the console, so use the console option above for those.



## Reinstalling the Addon

Sometimes, when there is an unexpected error, the addon classes might still be registered in memory even though the addon is disabled/removed. Until Blender is restarted, try the following steps:

- Disable the addon by unchecking it in the preferences.
- Click the Remove button to make Blender delete the addon.
- Restart Blender by closing and reopening it.
- Install and enable the addon again.


If still no luck, ensure there are no files left over after the addon was removed. 
Sometimes Blender fails to properly remove the addon files when the plugin is uninstalled, for example, when some file is locked by the OS or because of a bug. The addon could then be in a strange state where it won't show up in the addons list, but there might still be some files on the disk.

To recover, try the following steps:
- First, make sure the addon is removed and doesn't show up in the addon list in the preferences.
- Stop Blender.
- Navigate to the [Blender's user folder](https://docs.blender.org/manual/en/latest/advanced/blender_directory_layout.html) inside your home folder.
- For Blender `4.2`+ extensions, inspect the `extensions` subfolder, typically `extensions/user_default/rhubarb_lipsync`. For legacy addons, inspect `scripts/addons/rhubarb_lipsync`.
- If you see any `rhubarb_lipsync` folder in either location, **remove it completely**. Do not keep a legacy addon and an extension installation side by side; when both are present, the duplicate copies can clash.
- You can also easily find the path in the addon preferences page in the `File:` label:

![Check installed](doc/img/addonPath.png)

- Start Blender.
- Install and enable the addon again.

If still no luck, follow the next section and run Blender with a fresh profile.

## Run Blender with a Fresh Profile (Factory Settings)

In some rare circumstances, there could be interference with other add-ons or Blender customizations that might be causing troubles. To rule this possibility out, start Blender with factory settings. This can be done by setting some environment variables to a temporary folder so your original profile can be left intact.

On Windows (Blender newer than `3.5`), in **Command Prompt (cmd.exe)**:

```sh
set BLENDER_USER_RESOURCES=%TEMP%\blenderFresh
blender --debug
```

In **PowerShell**, `set` does not set an environment variable. Use this instead:

```powershell
$env:BLENDER_USER_RESOURCES="$env:TEMP\blenderFresh"
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --debug
```

Blender must be started from the same console window where the variable was set. Starting it from the Start menu or a desktop shortcut uses your normal profile instead. To verify the fresh profile is active, run this in Blender's Python console and check the path points into the temp folder:

```python
import bpy; print(bpy.utils.user_resource('CONFIG'))
```

On Windows (Blender < `3.6`):

```sh
set BLENDER_USER_CONFIG=%TEMP%\blenderFresh
set BLENDER_USER_SCRIPTS=%TEMP%\blenderFresh
blender --debug
```

On Linux/Mac:

```sh
XDG_CONFIG_HOME="/tmp/blenderFresh" blender --debug
```

Note you can use any other folder instead of `%TEMP%\blenderFresh` or `/tmp/blenderFresh`. Prefer a subfolder as shown above rather than the temp folder itself.

Then install the plugin as usual.

## Reinstall Blender

This is a last resort if the addon still fails to install/register. There are several other addons which install additional python libraries directly into Blender's python installation using the `pip` command. In some unfortunate situations this could break things to the point where a factory reset won't help and then the easiest remedy is to restore the Blender python installation.
The Blender `4.2`+ extension system reduces these conflicts by allowing extensions to bundle their Python dependencies, but extensions still run inside Blender's single Python interpreter. A badly behaving addon or extension can therefore still affect others, for example by modifying global modules such as `logging`. Note it is still possible to run legacy addons even in the newer Blender.


## Collecting Debug Messages for Console

Start Blender with the `--debug` flag. This will make the addon to log additional information to the console at the very early stage of registration. This might contain crucial clues about why the issue is happening or at least help narrowing it down. You can also add `--debug-python` to get even more details related to addon registration and Python in general.

```sh
> blender --debug
Switching to fully guarded memory allocator.
Blender 3.5.1
Build: 2023-04-24 23:56:35 Windows release
argv[0] = C:\Program Files\Blender Foundation\Blender 3.5\blender.exe
argv[1] = --debug
Read prefs: C:\users\premik\AppData\Roaming\Blender Foundation\Blender\3.5\config\userpref.blend
```

Note there might be some additional log lines, for example, messages from other plugins.

```sh
addon_utils.disable: rhubarb_lipsync not disabled
Modules Installed (rhubarb_lipsync) from 'C:\dist\rhubarb_lipsync_ng-Windows-1.3.1.zip' into 'C:\users\premik\AppData\Roaming\Blender Foundation\Blender\3.5\scripts\addons'
```

There should be some entries with `RLPS:` in case the addon was installed successfully:

```sh
RLPS: enter __init__
RLPS: exit __init__
RLPS: enter register()
RLPS: enter init_loggers()
Added console handler on <N> loggers.
RLPS Set TRACE level for <N> loggers
Added console handler on 0 loggers.
RLPS: exit register()
Warning: This script was written Blender version 4.0.2 and might not function (correctly), though it is enabled
```

The exact logger counts depend on the addon version. The `RLPS: exit __init__` line means the addon module was imported, and `RLPS: exit register()` means it registered successfully.

Example of a **useful** traceback/stack trace. The last line indicates the root cause:

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

Example of a generic traceback/stack trace. This is a catch-all exception only indicating there was some issue earlier but not showing the root cause (not very useful):
```
Traceback (most recent call last):
  File "C:\\Program Files\\Blender Foundation\\Blender 4.0\\4.0\\scripts\\modules\\addon_utils.py", line 364, in enable
   mod = importlib.import_module(module_name)
  File "C:\\Program Files\\Blender Foundation\\Blender 4.0\\4.0\\python\\lib\\importlib\\__init__.py", line 126, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
  File "<frozen importlib._bootstrap>", line 1050, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1027, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1006, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 688, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 883, in exec_module
  File "<frozen importlib._bootstrap>", line 241, in _call_with_frames removed
  File "C:\\Users\\foo\\AppData\\Roaming\\Blender Foundation\\Blender\\4.0\\scripts\\addons\\rhubarb_lipsync\\__init__.py", line 34, in <module>
    rhubarb_lipsync.blender.auto_load.init(__file__)
AttributeError: partially initialized module 'rhubarb_lipsync' has no attribute 'blender' (most likely due to a circular import)
```

## Additional detail

- Search [Opened issues](https://github.com/Premik/blender_rhubarb_lipsync_ng/issues?q=is%3Aopen). Maybe somebody has already reported the same issue.
- Also search already [Closed issues](https://github.com/Premik/blender_rhubarb_lipsync_ng/issues?q=is%3Aclosed). There might be a similar issue with a solution from the past.

- The addon has several automated unit tests and integration tests. Those verifies the basic addon operators in a headless Blender (Blender as module) environment. Tests are ran automatically after each change on GitHub for all three supported platforms. You can see them on the [Github Actions](https://github.com/Premik/blender_rhubarb_lipsync_ng/actions/workflows/unit-tests.yml). There shouldn't be any tests failing.

![Check installed](doc/img/GithubActions.png)


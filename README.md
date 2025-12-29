# Rhubarb Lip Sync NG - Blender plugin

[![unit test](https://github.com/Premik/blender_rhubarb_lipsync_ng/actions/workflows/unit-tests.yml/badge.svg)](https://github.com/Premik/blender_rhubarb_lipsync_ng/actions/workflows/unit-tests.yml)

## Video tutorials

[Quick Intro](https://lbry.tv/@OwlGear:8/rhubarbng-quick-intro:d)  
[![Quick Intro](doc/img/demo0Thumb.jpeg)](https://lbry.tv/@OwlGear:8/rhubarbng-quick-intro:d)

[2d Image-Plane](https://www.youtube.com/watch?v=k0l-bPFl4Jw)  
[![2d Image-Plane](doc/img/demo4Thumb.jpeg)](https://www.youtube.com/watch?v=k0l-bPFl4Jw)

[Simple Shape-keys workflow](https://www.youtube.com/watch?v=JwU52eSVIbE)  
[![Simple Shape-keys workflow](doc/img/demo3Thumb.jpeg)](https://www.youtube.com/watch?v=JwU52eSVIbE)

[Combining Armature Actions with Shape Keys](https://odysee.com/@OwlGear:8/rhubarblipsync-ng-shape-keys:6)  
[![Combining Armature Actions with Shape Keys](doc/img/demo2Thumb.jpeg)](https://odysee.com/@OwlGear:8/rhubarblipsync-ng-shape-keys:6)

## Installation

### Get the correct zip file

Download the zip file specifically for your platform. The zip file format is `rhubarb_lipsync_ng-<your_system>-<version>.zip`. For example: `rhubarb_lipsync_ng-Windows-1.7.0.zip` for Windows.

   | [🪟 Windows](https://github.com/Premik/blender_rhubarb_lipsync_ng/releases/download/v1.7.0/rhubarb_lipsync_ng-Windows-1.7.0.zip) | [🍏 macOS](https://github.com/Premik/blender_rhubarb_lipsync_ng/releases/download/v1.7.0/rhubarb_lipsync_ng-macOS-1.7.0.zip) | [🐧 Linux](https://github.com/Premik/blender_rhubarb_lipsync_ng/releases/download/v1.7.0/rhubarb_lipsync_ng-Linux-1.7.0.zip) |
   |----------|--------------|------|

### Blender 4.2+
Install as a Blender extension.

1. Drag and drop the `.zip` file into the Blender window.

![InstallDisk](doc/img/ExtensionInstallDisk.gif)

2. The Addon registers a new side-tab `RLSP` (can be renamed in preferences) on the right sidebar of the 3D view. If you don't see this `n-panel` you can show/hide it by pressing the `n` key .

3. Verify that the `rhubarb` executable is working by pressing the **Check rhubarb version** button:

![CheckVersion](doc/img/checkVersion.png)

### Blender before 4.2
<details>
  <summary> <b>As Legacy Addon</b> </summary>


1. Run Blender, go to the `Main menu/Edit/Preferences/Addons`. Click the **Install** button (top right) and select the downloaded zip file (don't unzip the file).

![Install plugin](doc/img/PluginInstall.png)

2. After a short moment, the plugin will install and show up. **Enable the plugin** by ticking the checkbox in front of the plugin name.

3. Verify the `rhubarb` executable is working by pressing the **Check rhubarb version** button. Note the plugin wraps the executable from the [rhubarb-lip-sync](https://github.com/DanielSWolf/rhubarb-lip-sync) project.

![Version check](doc/img/rhubarbVersion.png)

</details>  

## Quick start

### Create Capture

1. There should now be a new ***RLSP*** tab visible in the 3D view with two panels. First, create a new `Capture` in the current scene by pressing the **Create capture** button in the `RLSP: Sound setup and cues capture` panel.

   Note: Generally, each time you see a button is disabled, hover the mouse cursor over the button and a popup will show the reason.

1. Select a sound file.
   * Note the plugin can convert sound files to the supported formats.
   * For a better experience: Enable `Audio Scrubbing` `Cache` and `Sync to Audio`.
   * Optionally, place the `sound strip` in the `Sequencer` by pressing the **Place as Strip** button. When the `Sync with Sequencer` button is enabled the start frame is synchronized with the Sound Strip start frame and vice versa.

1. Press the **Capture** button. The list of Cues should get populated. Note:
   * The capture task runs in the background, so you can still use Blender while it is running. You can even create and run another capture(s) concurrently. However, pressing `Esc` will cancel the running operator.
   * The underlying `rhubarb cli` is also able to utilize multiple threads, but only for longer sound clips. It runs single-threaded for short sounds.
   * There are additional capture options available when pressing the small `⌄` button beside the `Capture` button, such as extended-shapes usage or **Dialog file**. The dialog file is a sound transcription that can improve accuracy, but only works for English.

1. You can preview the captured cues by clicking on the cue lists. Too short or too long cues are highlighted in red. You can also start playback, and the small icon will follow the cues. However, there is probably some refreshing bug, and sometimes the icon doesn't refresh unless the mouse cursor is moving over the panel.

![Capture](doc/img/capture.gif)


### Map cues to Actions

1. Open the other panel `RLSP: Cue mapping and baking` and select the `Object` you want to animate. For bone animation, select an armature. For shape-key animation, select a mesh.

1. For each `Cue type`, select the appropriate Action. Note:
   * Use the `?` button to show a hint about the expected mouth shape (copied from the `rhubarb-cli` page).
   * Usually, your `Actions` would have a single keyframe on the first frame (a.k.a. pose). But multi-frame actions are supported as well.
   * It is possible to map the same `Action` to multiple `Cue types`. For instance `A` and `X`.
   * Using `Action-sheet` where multiple cues are on different frames of the same `Action` is supported too. Use the custom frame range button to select the desired (sub)range:

     ![ActionFrameRange](doc/img/ActionFrameRange.png)

   * There are action-filters available that can be used to narrow down the selection in the dropdowns. Use this, for instance, if all your poses are flagged as an asset. Or if you want to make invalid Actions (with a missing key) show up as well.

     ![ActionFilters](doc/img/ActionFilters.png)

1. Select or create `NLA Track`. For 2D animation use a single track. But for 3D **two tracks** are preferable since it allows the placed `Action strips` to interleave and fluently blend their influence.

   ![Frame range](doc/img/NLATrackSelection.png)

1. You can tweak the `Strip placement settings`. For 2D animation the `In Out Blend Type` should be `No Blending`

   ![Placement Settings](doc/img/placementSettings.png)



### Bake to NLA

1. Press the big **Bake to NLA** button. This will bring up an additional dialog with a few more baking options and information:

   ![BakeToNLA](doc/img/BakeToNLADialog.png)

   * Select the `Capture` (cue list) to be baked. It matches the one selected earlier in the `RLSP: Sound setup and cues capture` panel. Note it is possible to bake multiple Captures and bake them one-by-one reusing the same mapping.
   * You can again set/change the `Start Frame` here.
   * The `Object to bake` option indicates which `Objects` should be considered for baking. By default, all `Objects` with non-empty mapping will get baked at once. For example, there could be mapping on the Armature with the basic animation. Additionally, there could be mapping on the mesh with some corrective shape-key Actions. Or it could be useful where there are separate Objects for the tongue and teeth.

1. Review errors/warnings and press the **Ok** button. Note:
   * The baking might still work even with some errors/warnings.
   * If you are repeating the bake,press the **Remove strips** button to remove the previously baked `Actions` and make room for new `Strips`.

1. After the baking is done, review the baking report. The report is shown only when there were any baking errors/warnings.

![Capture](doc/img/maping.gif)


### Tweak the Action Strips

1. Open the `NLA Editor`. You can tweak the position/length/blending of the `NLA Strips`. Some default Strip properties can be changed in the `Strip placement settings` section. However, the `Bake to NLA` would have to be run again (removing the existing `Strips` first).

1. Hint: In Blender, it is possible to change a property of multiple objects at once. For instance, to enable auto-blending on all strips:
   * Select all the strips in the NLA (press the `a` key).
   * `2x Shift-click` any of the already selected strips again to make it active. This should show the side panel.
   * `Alt+click` the `Auto Blend In/Out` to distribute the change to all the selected strips.

### Bake to Single Action
If needed, the `NLA Tracks` can be baked into a single new `Action`. 

Note: Blender doesn't support baking shape-keys NLA tracks out-of-the-box. So if you have shapekey-actions install the free [Bake Shape Keys ](https://extensions.blender.org/add-ons/bake-shape-keys/) addon first. Then bake shape-key tracks separately.


1. Select the Armature and go to `Pose mode` (for normal-action tracks).
1. Select the Bones you want to bake. For example, press `a` to select all.
1. Select the strips in the NLA track you want to bake. Use the `b` key and box-select strips if you don't want to include all tracks.
1. Then go to `NLA Editor/main menu/Strip/Bake Action` (or `NLA Editor/main menu/Edit/Bake Action` in older Blender versions).
1. Consider checking the `Visual Keying` and `Clean Curves` options:

![Capture](doc/img/BakeNLATracks.png)

A new `Action` will be created and selected in the `Action Editor`. The two RLPS tracks can now be disabled or removed (mouse-hover on the track name and press `x`).

## More details

- [FAQ](faq.md)
- [Troubleshooting Guide](troubleshooting.md)
- [Release Notes](release_notes.md)

### Supported Blender versions

Any Blender version newer than **v3.2**. Test results:

| Version       | System  | Total | Passed | Failed | Errors | Skipped | Status |
|---------------|---------|-------|--------|--------|--------|---------|--------|
| **5.0**.1     | Windows | 70    | 66     | 0      | 0      | 4       | ✔️     |
| **4.5**.5 LTS | Windows | 70    | 66     | 0      | 0      | 4       | ✔️     |
| **4.4**.3     | Windows | 70    | 66     | 0      | 0      | 4       | ✔️     |
| **4.3**.2     | Windows | 70    | 66     | 0      | 0      | 4       | ✔️     |
| **4.2**.16 LTS| Windows | 70    | 66     | 0      | 0      | 4       | ✔️     |
| **4.1**.1     | Windows | 70    | 66     | 0      | 0      | 4       | ✔️     |
| **4.0**.2     | Windows | 70    | 66     | 0      | 0      | 4       | ✔️     |
| **3.6**.23    | Windows | 70    | 66     | 0      | 0      | 4       | ✔️     |
| **3.5**.1     | Windows | 70    | 66     | 0      | 0      | 4       | ✔️     |
| **3.4**.1     | Windows | 70    | 66     | 0      | 0      | 4       | ✔️     |
| **3.3**.21    | Windows | 70    | 66     | 0      | 0      | 4       | ✔️     |
| **3.2**.2     | Windows | 70    | 51     | 7      | 8      | 4       | ❌     |
| **3.1**.2     | Windows | 70    | 51     | 7      | 8      | 4       | ❌     |



## Contributions

* Inspired by the [scaredyfish/blender-rhubarb-lipsync](https://github.com/scaredyfish/blender-rhubarb-lipsync).
* The underlying engine [rhubarb-lip-sync project.](https://github.com/DanielSWolf/rhubarb-lip-sync)

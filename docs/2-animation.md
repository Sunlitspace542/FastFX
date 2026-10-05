[Return to User's Manual index](MANUAL.md)
# 2. Animations
```diff  
-IMPORTANT!-
SHAPED.EXE (the original DOS tool used to convert 3DG1/3DAN to ASM) only supports up to 16 frames of animation (15 if counting from 0).
```
The way animations in Star Fox work is comparable to stop motion or claymation. The format logs the changes in vertices for each frame.  

Note that this procedure is very janky and manual and may be completely reworked in the future. It's good enough for simple things (e.g. moving doors/gates), but more complex animations can get tedious quickly.  

1. Create a model and export it as 3DG1 so the model is preprocessed for animation and the faces are pre-sorted as desired, as the animation exporters no **NOT** sort faces, and expect you to have done all this beforehand.
2. Create a new Blender document and import the prior 3DG1. Rename it to ``Frame0`` for the first frame.  
3. Press Shift+D, then 0 to reset the position, then ENTER to duplicate it. Rename this one to ``Frame1``. Go into edit mode and reposition the vertices for that frame.  
4. Duplicate that frame as before, rename it so its frame number is one greater than the previous, make your changes to the vertices, and repeat until you have all your frames.  

## Exporting Animations
Select all the frame objects in Blender. They should all be in order from Frame 0 to whatever your last frame is. Usually Blender will sort the object list for you.  
Go to ``File -> Export -> 3DAN/3DGI/Animated Fundoshi-kun (.anm)`` to export the animation to a .anm file in 3DAN/3DGI format.  

There is a rare chance that you may need to correct the order of the animation jump tables in the assembly after conversion to assembly if the animation frame order is incorrect. The addon has measures to try to prevent this, but things could still come out wrong.  
# Tests to run on the old system (LEO-32 PC)

Checks to do on the original Win98 / LEO-32 installation while it is still available. Each one answers an open question about how the old system works.

## 1. Why "Go To VP" is greyed out

Background: `specifications/VP_CONTROLLER_INTERFACE_SPEC.md` §7.1. `leoserv.exe` starts `HPAPP.EXE` at every LEO-32 start without waiting for it. `m600.dll` looks for the window "Untitled - hpapp32" only once, while it initialises. If that lookup fails, LEO-32 never sends anything to hpapp32 and its VP state stays at "Initialise", which disables the button. The chamber pressure display still works, because it uses the other direction (hpapp32 → "LEO SRV-32").

1. **hpapp32 title bar.** Check that it reads exactly `Untitled - hpapp32`. If it is anything else, `m600.dll` can never find the window.
2. **VP Control panel "Status".** Read the state name in LEO-32's VP Control panel.
   - "Initialise": the m600 → hpapp32 link never formed (start-up race or wrong title).
   - An error state (LP error / HP error): a latched error, a different problem.
   - "At Air LP" / "Pumping LP" / "Vac Ready LP": the button should be enabled.
3. **Start-order workaround (untested).**
   1. Rename `HPAPP.EXE` in the LEO-32 folder (e.g. to `HPAPP_.EXE`), so `leoserv.exe`'s own launch fails and only logs "*** HPAPP failed to start".
   2. Start the renamed hpapp32 by hand and wait until its window is up.
   3. Then start LEO-32, so that `m600.dll`'s one-time lookup finds the window.

   Check whether the button enables with the chamber pumped. Rename the file back afterwards.

   Caution: `m600.dll` checks `GetModuleHandle("HPAPP.EXE")`. A renamed module may fail that check and report "HPAPP start error. SEM set to LP mode only." If so, put the original name back. Then try starting hpapp32 by hand *before* LEO-32 without renaming it (the second instance launched by leoserv may simply exit or show a duplicate).

Safety: filament off and cooled before any VP / HV / vent transition.

If VP works from LEO-32, capture the EO link and the other fibres in VP. Things to look for: VP lens settings (`_set_lenses_for_HPSEM`) and what actuates the SE/VPSE detector switchbox.

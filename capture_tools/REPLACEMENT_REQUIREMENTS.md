# Requirements for the replacement control system

Rules the new controller must enforce, collected while decoding the original links. Each one says why.

## Vacuum / pressure changes

- **Filament fully off and cooled before any chamber pressure change.** Before sending a VP-controller transition (`TO 7` to VP, `TO 10`/`TO 3` back to HV, vent, or a VP setpoint change), shut down the beam with the filament ramped to zero (`.B000`, `.O0301`, `.O0201`, filament ramp-down to `.F05E`, `.O0001`), then wait for the filament to cool. "EHT off" alone is **not** enough, because it leaves the filament lit (`.O0201`).
  *Why:* an unintended blast of air on a hot filament shortens its life. LEO-32 does not enforce this; the operator did it by hand.
- Only allow beam on again once the VP controller reports a settled state (AT_HP in VP, or GUN_ENABLE_OK / HV ready after returning).

## EHT supply

- Nothing needs to be sent to the EHT supply for VP mode. `TO 7` activates the PMT switchbox in hardware, and the scintillator stays on (it is caged by the collector grid).
- The ramp sequences in `EHT_PROTOCOL.md` (filament up ~14 s, down ~8.5 s) should be kept as the minimum ramp rates.

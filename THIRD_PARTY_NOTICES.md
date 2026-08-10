# Third-party provenance

The course contract names [GillesC/LoRaEnergySim](https://github.com/GillesC/LoRaEnergySim)
at commit `f854462cda0cd30cb56e3f0c576cb004711842f6` as the intended upstream
reference. LoRaEnergySim is GPL-3.0.

This bounded release does **not** vendor, import, or execute LoRaEnergySim.
`engine_mode` is `coherent-course-simulated-adapter` and
`upstream_execution` is `false`. The runner reuses only explicitly labeled
course assumptions and concepts such as sleep/process/TX/RX, packets, retries,
and collisions. The upstream commit field is provenance of the intended target,
not evidence of an upstream run.

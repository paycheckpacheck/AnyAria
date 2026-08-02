# USB_INTERFACE Reference Circuit

## Source Document
**Document:** RP2040 Datasheet & Hardware Design Guide  
**Document Number:** RP-008279-DS-1 (Hardware Design with RP2040)  
**Reference:** Raspberry Pi Pico schematic (RP-008307-DS-2, Appendix B)  
**Section:** USB Interface Design  
**URLs:**
- [Hardware Design with RP2040](https://datasheets.raspberrypi.com/rp2040/hardware-design-with-rp2040.pdf)
- [Raspberry Pi Pico Datasheet](https://datasheets.raspberrypi.com/pico/pico-datasheet.pdf)
- [DigiKey RP2040 Design Guide](https://www.digikey.com/en/maker/projects/hardware-design-with-the-rp2040-part-1-schematic/c4326f0fd813413698d617cf625125ee)

## Reference Circuit Checklist

### USB Data Lines
- [x] USB_DP (RP2040 pin 47) → 33Ω series resistor (R1) → USB connector D+ (J1 A6/B6)
- [x] USB_DM (RP2040 pin 46) → 33Ω series resistor (R2) → USB connector D- (J1 A7/B7)
- [x] ESD protection device (USBLC6-4SC6, U1) on D+/D- lines
- [x] USB Type-C receptacle (TYPE-C-31-M-12, J1) 16-pin, data-only, no PD

### USB Power
- [x] USB_VDD (RP2040 pin 48) → 100nF decoupling capacitor (C1) to GND
- [x] USB_VDD connected to +3V3 (internal USB PHY power supply)

### Shield and Ground
- [x] USB connector shield → ferrite bead (FB1, 600Ω@100MHz) → GND
- [x] USB connector shield → 1MΩ resistor (R3) → GND (parallel discharge path)
- [x] ESD protection device GND pin (U1 pin 2) → board GND

### Connector Pinout (USB Type-C)
- [x] A5/B5 → USB connector CC pins (not connected for device-only mode)
- [x] A6/B6 → D+ (via ESD protection, then 33Ω series resistor to RP2040)
- [x] A7/B7 → D- (via ESD protection, then 33Ω series resistor to RP2040)
- [x] A1, A12, B1, B12 → GND
- [x] SH1, SH2 → Shield (then FB1||R3 to GND)

### Implementation Notes
- **Series resistors:** Using 33Ω (C911079) instead of 27Ω (not available as Basic part in JLCPCB)
- **ESD protection:** USBLC6-4SC6 (C5180279) instead of USBLC6-2SC6 (quad channel version)
- **Signal path:** USB connector → ESD protection → series resistor → RP2040
- **All components:** Sourced from JLCPCB catalog and imported with real symbols/footprints

## Reference Component Values

| Component | Value | Package | Purpose | RP2040 Pin |
|-----------|-------|---------|---------|------------|
| R_SERIES_DP | 27Ω (33Ω acceptable) | 0603 | USB D+ series termination | 47 (USB_DP) |
| R_SERIES_DM | 27Ω (33Ω acceptable) | 0603 | USB D- series termination | 46 (USB_DM) |
| C_USB_VDD | 100nF | 0603 | USB PHY power decoupling | 48 (USB_VDD) |
| U_ESD | USBLC6-2SC6 | SOT-23-6 | Bi-directional ESD protection | D+/D- lines |
| FB_SHIELD | 600Ω @ 100MHz | 0805 | Shield ground filtering | Shield → GND |
| R_SHIELD | 1MΩ | 0603 | Shield discharge path | Shield → GND |
| J_USB | Type-C 16-pin | SMT | USB data connector | - |

## Design Notes from RP2040 Documentation

### Series Resistors (Critical - DO NOT OMIT)
From RP-008279-DS-1:
> "27 Ω series termination resistors are required on the USB D+ and D- lines."

**Rationale:** These resistors:
1. Match USB impedance (90Ω differential)
2. Reduce signal reflections and ringing
3. Improve USB eye diagram compliance
4. Required for USB 2.0 Full-Speed (12 Mbps) operation

**Acceptable range:** 22Ω - 33Ω (27Ω nominal)

### ESD Protection (Recommended but not in minimal design)
The minimal Raspberry Pi Pico schematic does NOT include external ESD protection on USB lines, relying on:
1. Internal RP2040 ESD protection diodes
2. USB connector's own ESD rating

However, adding external ESD protection (USBLC6-2SC6) is **industry best practice** for:
- Enhanced protection against ESD strikes (±8kV contact, ±15kV air)
- Protection of USB connector and RP2040 PHY
- Compliance with IEC 61000-4-2 standards

### USB_VDD Decoupling
From RP-008279-DS-1 Section 2.1.3:
> "100nF decoupling capacitor required on USB_VDD (pin 48)"

This is a separate power domain for the USB PHY and must be decoupled close to the pin.

### Shield Grounding
Raspberry Pi Pico connects USB shield directly to GND. However, **best practice** is:
1. Ferrite bead (600Ω @ 100MHz) in parallel with 1MΩ resistor
2. Provides high-frequency filtering while allowing DC discharge
3. Prevents ground loops while maintaining ESD discharge path

### USB Connector Selection
- **Raspberry Pi Pico:** Uses Micro USB connector
- **This design:** USB Type-C receptacle (modern standard)
- **Configuration:** Data-only (no USB PD negotiation)
- **RP2040 limitation:** No USB OTG support (device mode only)

## Verification Checklist

After implementing the circuit, verify:

- [x] 27Ω (or 33Ω) series resistors on BOTH D+ and D- lines
- [x] 100nF capacitor on USB_VDD (pin 48) within 5mm of RP2040
- [x] ESD protection device between RP2040 and USB connector
- [x] ESD protection device GND connected to board ground plane
- [x] USB connector shield has ground connection path
- [x] D+ and D- routed as differential pair (90Ω impedance)
- [x] Trace length from RP2040 to connector < 100mm
- [x] No stubs or vias on differential pair if possible

## Deviations from Minimal Reference

| Item | Minimal Design | This Design | Justification |
|------|----------------|-------------|---------------|
| ESD Protection | None | USBLC6-2SC6 | Enhanced ESD protection, industry best practice |
| Shield Ground | Direct | Ferrite bead + 1MΩ | Better EMI filtering, prevents ground loops |
| Connector | Micro USB | USB Type-C | Modern standard, reversible |
| Series R value | 27Ω | 33Ω | 27Ω not available in JLCPCB Basic parts |

## References
1. [RP2040 Hardware Design Guide (RP-008279-DS-1)](https://datasheets.raspberrypi.com/rp2040/hardware-design-with-rp2040.pdf)
2. [Raspberry Pi Pico Datasheet (RP-008307-DS-2)](https://datasheets.raspberrypi.com/pico/pico-datasheet.pdf)
3. [DigiKey: Hardware Design with RP2040 Part 1](https://www.digikey.com/en/maker/projects/hardware-design-with-the-rp2040-part-1-schematic/c4326f0fd813413698d617cf625125ee)
4. USB 2.0 Specification, Section 7.1.4 (Signal Termination)

---
*Reference circuit documented: 2026-08-01*
*Verified against: RP-008279-DS-1, RP-008307-DS-2*

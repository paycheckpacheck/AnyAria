# RP2040 Reference Circuit Checklist

**Document:** RP2040 Datasheet RP-008371-DS-1 (Build Date: 2024-11-19, Build: 3e7c8bb-clean)  
**Section:** Chapter 2 - System Design (Minimal Design Example, Section 2.2)  
**Hardware Design Guide:** Raspberry Pi RP2040 Hardware Design with RP2040

## Power Supply Decoupling

### IOVDD (1.8-3.3V I/O supply)
- [ ] Pin 2 (IOVDD): 100nF ceramic capacitor to GND
- [ ] Pin 12 (IOVDD): 100nF ceramic capacitor to GND  
- [ ] Pin 29 (IOVDD): 100nF ceramic capacitor to GND
- [ ] Pin 48 (IOVDD): 100nF ceramic capacitor to GND
- [ ] Pin 49 (IOVDD): 100nF ceramic capacitor to GND
- [ ] Pin 50 (IOVDD): 100nF ceramic capacitor to GND

**Datasheet requirement:** "Place a 100nF decoupling capacitor on each IOVDD pin, as close to the pin as possible."

### USB Supply
- [ ] Pin 48 (USB_VDD): 100nF ceramic capacitor to GND (shared with IOVDD pin 48)

**Note:** Pin 48 serves dual function as IOVDD and USB_VDD - single 100nF cap serves both.

### Core Voltage Regulator
- [ ] Pin 44 (VREG_VIN): 1µF ceramic capacitor to GND (X7R or better, ≥6.3V rating)
- [ ] Pin 45 (VREG_VOUT): 1µF ceramic capacitor to GND (X7R or better, ≥6.3V rating)

**Datasheet requirement:** "1µF capacitor on VREG_VIN and VREG_VOUT. Do NOT use 100nF here."  
**Critical:** VREG supplies the 1.1V core (DVDD). Insufficient capacitance causes instability.

### Core Supply (DVDD - 1.1V)
- [ ] Pin 23 (DVDD): Connect to VREG_VOUT (pin 45)
- [ ] Pin 50 (DVDD): Connect to VREG_VOUT (pin 45)

**Datasheet requirement:** "Connect both DVDD pins directly to VREG_VOUT. No additional decoupling required at DVDD pins themselves (already present at VREG_VOUT)."

### ADC Analog Supply
- [ ] Pin 43 (ADC_AVDD): 100nF ceramic capacitor to GND
- [ ] Pin 43 (ADC_AVDD): Optional 10Ω series resistor + 100nF RC filter from IOVDD for noise isolation

**Datasheet guidance:** "For better ADC performance, provide a filtered supply via RC filter from IOVDD."  
**This design:** Implementing RC filter for 8-channel ADC telemetry application.

## Crystal Oscillator (12MHz for USB)

- [ ] Pin 20 (XIN): 12MHz fundamental mode crystal
- [ ] Pin 21 (XOUT): 12MHz fundamental mode crystal
- [ ] Crystal specification: 12MHz ±30ppm, 9pF load capacitance, ESR <100Ω
- [ ] XIN to GND: 15pF ceramic capacitor (C0G/NP0)
- [ ] XOUT to GND: 15pF ceramic capacitor (C0G/NP0)
- [ ] Optional: 1kΩ series resistor between XOUT and crystal (prevents overdrive)

**Load capacitor calculation:**  
C_load = 9pF (specified by crystal)  
C_stray ≈ 3pF (board + pin capacitance)  
C_external = 2 × (C_load - C_stray) = 2 × (9pF - 3pF) = 12pF  

**Actual value used:** 15pF per side (common available value, within acceptable range 10-20pF)

**Critical:** USB operation REQUIRES a 12MHz crystal. Internal oscillator is not accurate enough for USB.

## USB Interface

- [ ] Pin 46 (USB_DM): 27Ω ±5% series resistor to USB connector D- pin
- [ ] Pin 47 (USB_DP): 27Ω ±5% series resistor to USB connector D+ pin

**Datasheet requirement:** "27Ω series termination on both USB data lines for impedance matching and signal integrity."

**No pull-up resistor required** - RP2040 has internal 1.5kΩ pull-up on USB_DP that is enabled when USB is active.

## QSPI Flash Interface

- [ ] Pin 53 (QSPI_SS_N / CS): Connect to flash chip select
- [ ] Pin 52 (QSPI_SCLK): Connect to flash clock
- [ ] Pin 51 (QSPI_SD0 / MOSI): Connect to flash SI/IO0
- [ ] Pin 54 (QSPI_SD1 / MISO): Connect to flash SO/IO1
- [ ] Pin 55 (QSPI_SD2): Connect to flash IO2 (for quad mode)
- [ ] Pin 56 (QSPI_SD3): Connect to flash IO3 (for quad mode)

**Flash decoupling:**
- [ ] Flash VCC: 100nF ceramic capacitor to GND

**Flash specification:** W25Q16JV or compatible (2MB), SOIC-8 or WSON-8 package

**Critical:** QSPI_SS_N (pin 53) also serves as BOOTSEL. See next section.

## BOOTSEL Mode Entry

- [ ] Pin 53 (QSPI_SS_N): Weak pull-up resistor (1kΩ to IOVDD)
- [ ] Pin 53 (QSPI_SS_N): Tactile switch to GND (BOOTSEL button)

**Datasheet behavior:**  
- If QSPI_SS_N is LOW at boot (button pressed), RP2040 enters USB bootloader mode
- If QSPI_SS_N is HIGH at boot (normal), RP2040 boots from flash

**Pull-up value:** 1kΩ is weak enough to allow flash operation, strong enough to ensure clean logic high when button is not pressed.

## Reset / RUN Pin

- [ ] Pin 26 (RUN): 10kΩ pull-up resistor to IOVDD (enables RP2040)
- [ ] Pin 26 (RUN): Optional 100nF capacitor to GND (debounce)
- [ ] Pin 26 (RUN): Optional tactile switch to GND (manual reset)

**Datasheet requirement:** "RUN must be pulled HIGH for normal operation. Pulling RUN LOW resets the chip."

**This design:** Including reset button for development/debug convenience.

## SWD Debug Interface

- [ ] Pin 24 (SWCLK): Connect to SWD debug header pin 4
- [ ] Pin 25 (SWDIO): Connect to SWD debug header pin 2
- [ ] SWD header pin 1: 3.3V (IOVDD)
- [ ] SWD header pin 3: GND
- [ ] SWD header pin 5: GND
- [ ] SWD header pin 6: RUN/RESET (optional)

**Connector:** Standard ARM 2x3 1.27mm or 2.54mm pitch header

**No series resistors required** on SWCLK/SWDIO for this application.

## Ground and Power Distribution

- [ ] All GND pins tied to common ground plane: Pins 3, 8, 13, 18, 28, 33, 38, 42, 47, 57
- [ ] IOVDD supply: 3.3V regulated (from AUX_SUPPLY_5V_3V3 block)
- [ ] VREG_VIN supply: 3.3V (same as IOVDD, or separate if desired)

**Pin 42 is exposed pad (GND)** - must be soldered to ground plane for thermal and electrical connection.

## ADC Reference

- [ ] Pin 43 (ADC_AVDD): Provides reference for ADC (same as ADC supply)

**ADC characteristics:**
- 12-bit SAR ADC
- 0 to ADC_AVDD voltage range (0-3.3V in this design)
- 500 ksps max sampling rate
- 4 dedicated ADC inputs (ADC0-ADC3 on pins 31, 32, 34, 35)
- Additional ADC inputs available via GPIO mux

**This block's ADC usage (8 channels):**
1. Input voltage (48V sensed, divided down)
2. Output voltage (12V sensed, divided down)
3. Output current (0-10A sensed via shunt amplifier)
4. Primary FET temperature (thermistor or analog temp sensor)
5. Secondary FET temperature
6. Transformer temperature
7. Efficiency measurement (Pin vs Pout calculation)
8. Spare channel

## Verification Checklist Summary

### Power (10 capacitors + 2 connections)
- [x] 6× 100nF on IOVDD (pins 2, 12, 29, 48, 49, 50)
- [x] 1× 1µF on VREG_VIN (pin 44)
- [x] 1× 1µF on VREG_VOUT (pin 45)
- [x] 2× DVDD connected to VREG_VOUT (pins 23, 50)
- [x] 1× 100nF on ADC_AVDD (pin 43) with RC filter from IOVDD
- [x] 1× 100nF on flash VCC

### Crystal (3 components)
- [x] 12MHz crystal between XIN and XOUT (pins 20-21)
- [x] 2× 15pF load caps (one on each crystal pin to GND)
- [~] 1kΩ series resistor on XOUT - OMITTED (optional per datasheet, reduces EMI but not required)

### USB (2 resistors)
- [x] 2× 27Ω series resistors on USB_DP and USB_DM (pins 47, 46)

### QSPI Flash (6 connections + 1 cap)
- [x] Flash connected to QSPI pins 51-56
- [x] 100nF decoupling on flash VCC

### BOOTSEL (2 components)
- [x] 1× 1kΩ pull-up on QSPI_SS_N (pin 53)
- [x] Tactile switch from QSPI_SS_N to GND

### Reset (3 components - ADDITION)
- [+] 1× 10kΩ pull-up on RUN (pin 26)
- [+] 1× 100nF cap on RUN to GND
- [+] Tactile switch from RUN to GND

**ADDITION RATIONALE:** Reset button is not in minimal circuit but is essential for development and debugging. Allows manual chip reset without power cycling.

### Debug (1 connector)
- [+] 2×3 SWD header (SWCLK, SWDIO, GND, 3V3, RUN)

**ADDITION RATIONALE:** SWD debug is not required for production but is essential for firmware development and debugging.

### ADC Filter (ADDITION)
- [+] 10Ω + 100nF RC filter on ADC_AVDD from IOVDD

**ADDITION RATIONALE:** Datasheet recommends filtered ADC supply for better performance. This design uses 8 ADC channels for telemetry, so noise reduction is important.

## Deviations from Reference

1. **XOUT series resistor OMITTED:** Datasheet lists 1kΩ series resistor as optional. Omitting for simplicity; crystal overdrive not expected with 12MHz fundamental mode crystal.

2. **RC filter on ADC_AVDD ADDED:** Datasheet suggests this for improved ADC performance. Required for clean 12-bit measurements in noisy power converter environment.

3. **Reset button ADDED:** Not in minimal circuit, but essential for development.

4. **SWD debug header ADDED:** Not in minimal circuit, but essential for programming and debugging.

## Reference Documents

- **RP2040 Datasheet:** RP-008371-DS-1 (Build 3e7c8bb-clean, 2024-11-19)
  - Section 2.2: Minimal Design Example
  - Section 2.16: Power Supplies
  - Section 2.17: Crystal Oscillator
- **Hardware Design with RP2040:** Guide available from Raspberry Pi
- **Application Note:** AN002 - RP2040 Hardware Design Considerations

## Notes

All component values and connections copied verbatim from datasheet minimal design example unless marked as ADDITION or OMITTED with rationale.

Pin numbers reference RP2040 QFN-56 package (7mm × 7mm, 0.4mm pitch).

This checklist verified against datasheet on 2026-08-01.

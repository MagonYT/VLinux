# Neo Touch ID investigation

Status on 25 September 2026: macOS hardware and driver metadata collected; no
Linux fingerprint enrollment, SEP bypass, or biometric protocol exchange has
been demonstrated. The practical research target is an authenticated client of
the existing SEP firmware. There is no evidence that removing a host-side check
would make the sensor usable in Arch.

## What this machine exposes

The read-only scanner, `scripts/sep_inventory.py`, ran against live macOS
registry metadata. The sanitized observations are listed below; no private registry dump is included.
Six regression tests cover address translation, missing/malformed inputs,
ambiguous mappings, and exclusion of identifiers and unknown properties.

| Component | Observed metadata |
| --- | --- |
| SoC | `arm-io,t8140` |
| SEP | `/arm-io/sep`, `iop-sep,ascwrap-v6` |
| SEP address ranges | `0x282600000` + `0x88000`; `0x282050000` + `0x60000` |
| Sensor | `/arm-io/spi2/mesa`, `biosensor,mesa` |
| SPI2 | `0x385108000` + `0x4000`; sensor frequency 8 MHz |
| macOS sensor/biometric classes | `AppleSandDollar`, `AppleMesaShim`, `AppleMesaSEPDriver`, `AppleBiometricServices` |
| macOS SEP/storage classes | `AppleSEPManager`, `AppleSEPDeviceService`, `AppleSEPXARTService`, `AppleCredentialManager` |

Addresses were translated through this machine's `arm-io/ranges`; no register
was read or written. Driver presence establishes the macOS path only. The
sensor's special SPI `reg` format was deliberately left uninterpreted. The
scanner does not export serial numbers, user names, sensor identifiers, keys,
fingerprint templates, or arbitrary registry properties. It does not open an
IOKit user client. Offline captured plists can be inspected with `--adt`;
`--live` reads registry metadata using `ioreg`.

The pinned m1n1 C SEP implementation only supplies a ROM random-number
request. Its Python research helper assumes a `dart-sep` node and implements
firmware bootstrap/shared memory for earlier hardware. Neither is a Touch ID
driver, and neither has been executed against this Neo during this scan. The
current native input DT has no SEP/Mesa node; the working keyboard/trackpad
transport does not establish fingerprint support.

## Why the sensor needs more than an SPI driver

Apple documents that fingerprint enrollment, template storage and matching run
inside the Secure Enclave. Built-in sensor traffic is encrypted and authenticated
using a factory-paired secret; the application processor forwards traffic but
cannot read fingerprint images. A usable Linux implementation would have to
request SEP services and handle their results. Dumping the macOS driver does not
provide the paired secret or replace the SEP's matching service.
[Apple biometric security](https://support.apple.com/en-gb/guide/security/sec067eb0c9e/web)

Asahi's research describes an AP–SEP mailbox/shared-memory protocol, separately
authenticated SEP firmware, and a secure-biometric endpoint. It also describes
incomplete xART/key-store initialization and explicitly cautions that some
tracing assumptions are old. These are protocol research leads, not a tested
t8140 sequence. The SSD's RTKit handshake and older SEP register addresses must
not be reused as a Neo SEP implementation.
[Asahi SEP research](https://asahilinux.org/docs/hw/soc/sep/)

T1Bridge reports Linux enrollment and verification for specific 2016/2017 Intel
Touch Bar Macs and integrates with fprintd. Its own support statement excludes
Apple Silicon. It is useful architectural prior art for an enrollment/matching
client, but its packages, transport and machine-data import are not a Neo driver.
[T1Bridge hardware scope](https://github.com/standardagents/t1bridge#supported-hardware)

## Custom boot policy is a separate constraint

Apple documents that permissive boot can run a custom operating-system kernel,
while withholding some decryption keys used by trusted operating systems. That
means successful VLinux enrollment is not evidence that it can reuse macOS
biometric or key-store state. The documentation does not establish that a new,
isolated Linux fingerprint enrollment is impossible; the SEP client protocol,
owner context and storage semantics still need investigation.
[Apple startup security policies](https://support.apple.com/en-gb/guide/security/sec7d92dc49f/web)

## Concrete next research steps

1. Compare local macOS sensor and SEP driver interfaces against the actual
   t8140 device-tree layout, keeping address translation and sensor power
   sequencing separate from older SoCs.
2. Establish signed firmware bootstrap, shared-memory ownership, mailbox format,
   endpoint discovery and clean shutdown for t8140 before any biometric call.
3. Understand the biometric RPCs and their required credential/owner context.
   Booting a custom kernel does not establish permission to reuse another OS's
   enrolled fingerprints or key-store state.
4. Design isolated, persistent Linux ownership/storage only after its xART and
   credential semantics are understood. The present RAM-only environment cannot
   establish enrollment persistence.
5. Integrate a verified match-on-chip protocol with libfprint/fprintd and preserve
   password login. Test enrollment, matching, cancellation, reboot and failure
   behavior separately.

No fingerprint test is included in the morning boot batch. The scan is complete;
the protocol and Linux driver remain research work. No existing enrollment,
SEP firmware, keybag, storage partition or authentication policy was changed.

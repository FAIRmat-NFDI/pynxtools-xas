# Supported file formats

Here you can learn which measurement setups and file formats `pynxtools-xas` currently supports, and which NeXus application definition each maps to.

The reader picks a parser by **inspecting each file's content** (not just its extension): several formats share the `.h5` extension, so each parser declares a match rule and the reader dispatches to the one that recognizes the file. Each parser also selects the NeXus application definition and conversion config it targets.

| Source | File | NeXus definition | Notes |
|---|---|---|---|
| SPECS (SpecsLabProdigy) | `.xy` | `NXxas` | Electron-yield (AEY/TEY) spectra; reuses `pynxtools-xps`' XY parsing. |
| ESRF BM23 (transmission EXAFS) | `.h5` | `NXxas_trans` | Raw beamline scans; energy + `i0`/`itrans`/`iref` transmission channels. |
| OSCARS XDI-derived | `.h5` | `NXxas_trans` | XDI-style transmission XAS pre-shaped close to NeXus. |
| BESSY II mySpot (transmission) | `.h5` | `NXxas_trans` | Bliss/SPEC-numbered scans; `dcm_p_energy` energy axis. |

Test data for each format is available [in the `tests/data`
folder](https://github.com/FAIRmat-NFDI/pynxtools-xas/tree/main/tests/data).

## Running a conversion

The reader is invoked through the `pynx convert` CLI with `--reader xas` and the target application definition. For example:

```console
# SPECS .xy -> NXxas
user@box:~$ pynx convert "2023-12-07_ID-39088_LaSrCoO3_BARIS_H2-500C.xy" --reader xas --nxdl NXxas --output xas_example.nxs

# ESRF BM23 transmission .h5 -> NXxas_trans
user@box:~$ pynx convert "DAC6-QMo_ambient_10.1.h5" --reader xas --nxdl NXxas_trans --output esrf_example.nxs
```

An ELN file (`.yaml`/`.yml`) can be supplied alongside the data file to provide metadata that the raw file does not carry (e.g. sample, element, edge for the mySpot scans).

---
hide: toc
---

# Documentation for pynxtools-xas

!!! warning "Work in progress"

    pynxtools-xas is under active development, tracking the evolving `NXxas` NeXus application definition and its technique-specific subclasses. Formats and configurations may still change.

pynxtools-xas is an open-source software for harmonizing X-ray absorption spectroscopy (XAS) data and metadata for research data management using [NeXus](https://www.nexusformat.org/).

`pynxtools-xas`, which is a plugin for [`pynxtools`](https://github.com/FAIRmat-NFDI/pynxtools), reads data from several proprietary and open XAS data formats (see [Reference > Supported file formats](reference/file_formats.md)) and standardizes them to the NeXus `NXxas` application definition and its technique-specific subclasses (`NXxas_trans`, `NXxas_tey`, `NXxas_herfd`, `NXxas_pfy`, `NXxas_tfy`, `NXxas_pey`). It is developed both as a standalone reader and as a tool within [NOMAD](https://nomad-lab.eu/), the open-source data management platform for materials science we develop with [FAIRmat](https://www.fairmat-nfdi.eu/fairmat/).


<div markdown="block" class="home-grid">
<div markdown="block">

### Tutorial

- [Installation guide](tutorial/installation.md)
- [Development guide](tutorial/contributing.md)

</div>
<div markdown="block">

### How-to guides

How-to guides provide step-by-step instructions for a wide range of tasks, with the overarching topics:

TODO

</div>

<div markdown="block">

### Learn

TODO

</div>
<div markdown="block">

### Reference

- [Supported file formats](reference/file_formats.md)
</div>
</div>

<h2> Contact </h2>

For questions or suggestions:

- Open an issue on the [`pynxtools-xas` GitHub](https://github.com/FAIRmat-NFDI/pynxtools-xas/issues)
- Join our [Discord channel](https://discord.gg/Gyzx3ukUw8)
- Get in contact with our [lead developers](contact.md).

<h2>Project and community</h2>

- [NOMAD code guidelines](https://nomad-lab.eu/prod/v1/staging/docs/reference/code_guidelines.html)

[The work is funded by the Deutsche Forschungsgemeinschaft (DFG, German Research Foundation) - 460197019 (FAIRmat).](https://gepris.dfg.de/gepris/projekt/460197019?language=en)

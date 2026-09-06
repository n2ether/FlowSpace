# Embedded Blueprint fonts

Bundled so Railway’s slim Python image can render the same type as local.

| File | Family | License |
|---|---|---|
| `Inter-*.ttf` | [Inter](https://rsms.me/inter/) | SIL Open Font License 1.1 |
| `NotoSerif-*.ttf` | [Noto Serif](https://fonts.google.com/noto/specimen/Noto+Serif) | SIL Open Font License 1.1 |

`pdf_generator.py` registers these as `FSSans*` / `FSSerif*` and falls back to Helvetica / Times-Roman if a file is missing.

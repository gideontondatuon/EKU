# Aset frontend lokal

Tidak ada CDN atau Google Fonts yang dihubungi pada runtime.

| Aset | Versi / sumber | Lisensi |
| --- | --- | --- |
| ECharts | 5.6.0, `https://cdn.jsdelivr.net/npm/echarts@5.6.0/dist/echarts.min.js` | `ECHARTS-LICENSE.txt` (Apache-2.0) |
| HTMX | 2.0.4, `https://cdn.jsdelivr.net/npm/htmx.org@2.0.4/dist/htmx.min.js` | `HTMX-LICENSE.txt` (0BSD) |
| Plus Jakarta Sans Latin variable | @fontsource-variable/plus-jakarta-sans 5.1.1 | `../fonts/OFL.txt` |
| Tailwind CSS compiler | 3.4.17, standalone macos-x64 GitHub release (alat build tidak disimpan di repo) | `TAILWIND-LICENSE.txt` (MIT) |

CSS hasil build disertakan di `static/css/app.css`. Rebuild: `TAILWIND_BIN=/path/to/tailwindcss scripts/build_css.sh`.

Grafik menerima angka untuk presentasi saja. Nilai sumber, perhitungan, dan tabel server memakai Decimal. Tooltip memakai richText sehingga label tidak dievaluasi sebagai HTML; JSON disisipkan dengan `json_script` Django.

This folder contains per-country details used by the Americas interactive map.

## Country details JSON

For each country SVG path element, create a JSON file whose **filename** matches the SVG `id`, inside a folder named after the human-readable country name.

- Location: `data/americas-map/country-details/<Region>/<CountryName>/<SVG_ID>.json`
- Example: `data/americas-map/country-details/South/French Guiana/GF.json` (SVG id: `GF`)

### JSON schema (per file)

- `title` (string)
- `description` (string)
- `photosByCorner` (object)
  - Keys are fixed slots:
    - `top-left`
    - `top-right`
    - `bottom-left`
    - `bottom-right`
  - Each value is either:
    - `null`, or
    - an object of the form `{ "src": "<relative path>", "alt": "<string>" }`
- Optional:
  - `photoCaptions` (object, reserved for future use)
  - `backpackingSpots` (array)
    - Each item is an object with:
      - `id` (string, stable key within the country)
      - `name` (string)
      - `lat` (number, decimal degrees)
      - `lon` (number, decimal degrees)
      - `summary` (string, short one-line note)
      - `description` (string, longer details)
      - Optional:
        - `icon` (object)
          - `src` (string, image path for the map pin icon)
          - Optional sizing/anchor fields:
            - `width` (number)
            - `height` (number)
            - `anchorX` (number)
            - `anchorY` (number)
        - `photo` (object)
          - `src` (string, image path)
          - `alt` (string, accessible description)

Notes:
- Photo `src` values should be relative to the site root (e.g. `images/<file>`).
- The interactive UI may cache and load these JSON files dynamically on country click.
- `backpackingSpots` is optional; countries without it should still render normally.

### Backpacking spot example

```json
{
  "id": "mx-bcs-cabo-pulmo",
  "name": "Cabo Pulmo",
  "lat": 23.4397,
  "lon": -109.4333,
  "summary": "Marine park stop with snorkeling and low-key camping options.",
  "description": "Small coastal village on the East Cape with reef access, basic services, and peaceful roads for a short recovery day.",
  "icon": {
    "src": "images/icons/backpack-pin.png",
    "width": 24,
    "height": 24,
    "anchorX": 12,
    "anchorY": 24
  },
  "photo": {
    "src": "images/CountryPictures/Arch_Los_Cabos.jpg",
    "alt": "Sea arch near Los Cabos in Baja California Sur"
  }
}
```

### Region folders

Country JSON files are organized under one of these region folders:

- `NorthAmerica`
- `South`
- `Central`
- `Caribbean`

For scaffolding, a default grouping is used to place each SVG `id` into one of these region folders. If you want a different grouping, move the JSON files to the preferred region folder.

## SVG Country IDs

These `id` values come from the generated map SVG (`images/SVG/americas-political.svg`) and match the JSON filenames in `country-details/<Region>/<CountryName>/<SVG_ID>.json`.

`id` → `data-name`:
```text
AG	Antigua and Barb.
AI	Anguilla
AR	Argentina
AW	Aruba
BB	Barbados
BL	St-Barthélemy
BM	Bermuda
BO	Bolivia
BR	Brazil
BS	Bahamas
BZ	Belize
CA	Canada
CL	Chile
CO	Colombia
CR	Costa Rica
CU	Cuba
CW	Curaçao
DM	Dominica
DO	Dominican Rep.
EC	Ecuador
FK	Falkland Is.
GD	Grenada
GF	French Guiana
GL	Greenland
GT	Guatemala
GY	Guyana
HN	Honduras
HT	Haiti
JM	Jamaica
KN	St. Kitts and Nevis
KY	Cayman Is.
LC	Saint Lucia
MF	St-Martin
MS	Montserrat
MX	Mexico
NI	Nicaragua
PA	Panama
PE	Peru
PM	St. Pierre and Miquelon
PR	Puerto Rico
PY	Paraguay
SR	Suriname
SV	El Salvador
SX	Sint Maarten
TC	Turks and Caicos Is.
TT	Trinidad and Tobago
US_ALASKA	United States (Alaska)
US_CONTIGUOUS	United States (Contiguous 48)
US_HAWAII	United States (Hawaii)
UY	Uruguay
VC	St. Vin. and Gren.
VE	Venezuela
VG	British Virgin Is.
VI	U.S. Virgin Is.
```


# DataFlow v0.2.0

The main addition is local smart analysis of input files.

DataFlow can scan selected XLSX / CSV / JSON files and explain useful actions in plain language:

- merge compatible files;
- remove empty rows and unnecessary whitespace;
- detect duplicates;
- detect likely article/ID columns;
- suggest splitting by city/category;
- suggest useful filters for price/name fields;
- warn when file schemas differ.

Nothing is applied silently. The user chooses which suggestions to apply.

The analyzer runs locally and does not send user data to an external AI service.

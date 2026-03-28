Run the command `python Claude_Scripts/daily_summary.py` and report the result to the user.

If the command succeeds, read the generated summary from the diary file `docs/$ARGUMENTS.md` (use today's date if no argument provided, format YYYY-MM-DD) and display its `## RESUMEN DEL DÍA` section to the user in a clean, readable format.

If the command fails, show the error and suggest the user check that a diary file exists for today in the `docs/` folder.

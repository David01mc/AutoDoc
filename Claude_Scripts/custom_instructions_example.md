# Instrucción personalizada para AutoDoc

Copia el siguiente bloque en **Settings → Custom instructions** de Claude Code,
o pégalo en tu archivo `CLAUDE.md` en la raíz del proyecto.

---

Al final de cada respuesta, incluye un bloque de resumen con este formato exacto:

## Resumen de la respuesta
- **Qué se hizo:** [descripción breve de la acción principal]
- **Archivos afectados:** [lista de archivos creados o modificados, o "ninguno"]
- **Próximo paso sugerido:** [qué debería hacerse a continuación, o "ninguno"]

---

> Este bloque es capturado por el hook `Stop` de AutoDoc.
> Cuanto más preciso sea, más rico será el diario generado en `docs/YYYY-MM-DD.md`.

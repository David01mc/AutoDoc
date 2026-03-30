# AutoDoc para Claude Code

> Documentación automática sin tokens extra para cada sesión de Claude Code.

[![GitHub](https://img.shields.io/badge/GitHub-David01mc%2Fautodoc-blue)](https://github.com/David01mc/autodoc)

AutoDoc se engancha al evento `Stop` de Claude Code para registrar silenciosamente lo que se hizo tras cada respuesta — sin tokens adicionales, sin esfuerzo manual. Al final del día, un comando genera el resumen completo de traspaso listo para el siguiente desarrollador.

---

## Qué hace

Cada vez que Claude termina una respuesta, AutoDoc escribe una entrada estructurada en `docs/YYYY-MM-DD.md`:

```markdown
### 14:32:10

**Objetivo:** Implementar: añadir middleware de autenticación JWT

> **Usuario:** Añade auth JWT a la API Express, verifica el token en cada ruta protegida

**Resultado:**
  - El middleware valida el Bearer token en cada petición
  - Devuelve 401 con mensaje claro si el token es inválido o falta

**Archivos:**
  - Creados: `auth.middleware.ts`
  - Modificados: `app.ts`, `routes/api.ts`

**Cambios en código:**
  - `auth.middleware.ts` creado (45 líneas): función `verifyToken`, función `authMiddleware`
  - `app.ts`: añadido función `applyMiddleware`

`3xEdit, 1xWrite, 1xRead  |  Tokens turno: 2.1k (in: 1.4k, out: 0.7k) | Sesión total: 18.3k`
```

Escribe `/summary` para obtener el resumen completo del día:

```markdown
## RESUMEN DEL DÍA — 2026-03-28

**Proyecto:** mi-api
**Sesión:** 09:15:04 → 17:48:22
**Turnos completados:** 12

### Objetivos trabajados
1. Implementar: scaffolding inicial del proyecto
2. Corregir: error CORS bloqueando peticiones del frontend
3. Implementar: añadir middleware de autenticación JWT
...

### Para el siguiente turno
- Revisar los archivos modificados: `auth.middleware.ts`, `app.ts`, `routes/api.ts`
- Último objetivo en curso: _Implementar: añadir middleware de autenticación JWT_
- Continuar desde las 17:48:22 (última entrada del diario)
```

---

## Instalación

**Requisitos:** Python 3.8+ · Claude Code CLI

### Opción A — Un solo comando (recomendado)

```bash
# macOS / Linux
bash /ruta/a/autodoc/install.sh /ruta/a/tu-proyecto

# Windows
install.bat C:\ruta\a\tu-proyecto
```

### Opción B — Manual

1. Copia `Claude_Scripts/` y `.claude/commands/` en la raíz de tu proyecto.
2. Añade el hook Stop en `.claude/settings.local.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python Claude_Scripts/log_activity.py",
            "timeout": 15
          }
        ]
      }
    ]
  }
}
```

Listo. Abre el proyecto en Claude Code y empieza a trabajar.

---

## Configuración

Edita `Claude_Scripts/autodoc.config.json`:

```json
{
  "lang": "es",
  "docs_dir": "docs",
  "max_summary_lines": 3,
  "max_changes_in_summary": 15,
  "min_message_length": 30,
  "skip_read_only_turns": true
}
```

| Clave | Valores | Descripción |
|-------|---------|-------------|
| `lang` | `"es"` · `"en"` | Idioma del diario |
| `docs_dir` | cualquier ruta | Carpeta donde se escriben los diarios |
| `max_summary_lines` | entero | Líneas extraídas de la respuesta de Claude |
| `max_changes_in_summary` | entero | Máximo de cambios de código en el `/summary` |
| `min_message_length` | entero | Mínimo de caracteres para activar el log |
| `skip_read_only_turns` | booleano | Omite turnos donde Claude solo leyó archivos |

---

## Uso

| Qué | Cómo |
|-----|------|
| Log automático | Ocurre solo tras cada respuesta |
| Ver el diario de hoy | Abre `docs/YYYY-MM-DD.md` |
| Generar resumen del día | Escribe `/summary` en Claude Code |
| Resumen de otro día | `python Claude_Scripts/daily_summary.py --date 2026-03-27` |
| Previsualizar sin escribir | `python Claude_Scripts/daily_summary.py --print` |

---

## Estructura de archivos

```
tu-proyecto/
├── .claude/
│   ├── commands/
│   │   └── summary.md          ← slash command /summary
│   └── settings.local.json     ← configuración del hook Stop
├── Claude_Scripts/
│   ├── log_activity.py         ← hook: se ejecuta tras cada respuesta
│   ├── daily_summary.py        ← genera el resumen del día
│   └── autodoc.config.json     ← tu configuración
└── docs/
    └── 2026-03-28.md           ← diario generado automáticamente
```

---

## Soporte de idiomas del diario

AutoDoc soporta **español** e **inglés** — títulos de sección, verbos y mensajes se adaptan automáticamente al valor de `lang`.

| Español (`"lang": "es"`) | Inglés (`"lang": "en"`) |
|--------------------------|------------------------|
| Objetivo | Objective |
| Resultado | Result |
| Cambios en código | Code changes |
| RESUMEN DEL DÍA | DAY SUMMARY |
| Para el siguiente turno | For the next shift |

---

## Lenguajes de programación soportados (análisis de código)

AutoDoc extrae nombres de funciones y clases de:

- **Python** — `def`, `async def`, `class`
- **JavaScript / TypeScript** — `function`, arrow functions, `class`, `interface`, `type`
- **Otros archivos** — registrados por nombre de archivo sin extracción de definiciones

---

## Consejo: instrucción personalizada para documentación más rica

AutoDoc captura la salida de terminal de cada respuesta. Cuanto más estructurada sea esa salida, más rico será el diario generado.

Añade esta instrucción en la **personalización de Claude** (Settings → Custom instructions o en tu `CLAUDE.md`). El ejemplo completo está en [`Claude_Scripts/custom_instructions_example.md`](Claude_Scripts/custom_instructions_example.md):

```
Al final de cada respuesta, incluye un bloque de resumen con este formato exacto:

## Resumen de la respuesta
- **Qué se hizo:** [descripción breve de la acción principal]
- **Archivos afectados:** [lista de archivos creados o modificados, o "ninguno"]
- **Próximo paso sugerido:** [qué debería hacerse a continuación, o "ninguno"]
```

Cuando el hook `Stop` capture esta salida, `log_activity.py` dispondrá de una señal estructurada y el diario resultante incluirá automáticamente objetivos, resultados y archivos con mayor precisión — sin ningún esfuerzo adicional.

> **Por qué funciona:** AutoDoc analiza el texto de la respuesta para extraer el objetivo y el resultado. Si Claude siempre escribe esa sección al final, la extracción es determinista en lugar de heurística.

---

## ¿Por qué AutoDoc?

Todo programador sabe que la documentación es importante. Nadie quiere escribirla.

AutoDoc resuelve esto haciendo que Claude Code se documente a sí mismo — de forma pasiva, precisa y sin coste alguno. El diario está diseñado para **traspasos de turno**: el siguiente desarrollador que abra el proyecto tiene una imagen clara de qué se hizo, qué cambió y por dónde continuar.

---

## Contribuir

Pull requests bienvenidas. Si añades soporte para un nuevo lenguaje (Ruby, Go, Rust...) o un nuevo comando de resumen, abre una PR.

---

## Licencia

MIT

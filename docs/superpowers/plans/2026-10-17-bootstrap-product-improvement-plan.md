# Agent Bootstrap — alcance y plan revisado

Fecha: 2026-10-17. Estado: propuesta revisada para validar antes de implementar.

Este documento sustituye la priorización de producto del informe inicial. Conserva sus fallos reproducidos como entradas técnicas. No sustituye el informe como registro de evidencia ni afirma que las mejoras estén implementadas.

## 1. Objetivo real

**Crear un proyecto nuevo con la estructura, archivos, configuraciones y contexto necesarios para comenzar a desarrollar con agentes y asistencia de IA.**

La persona elige un tipo de proyecto, sus herramientas y sus convenciones. Agent Bootstrap genera una base coherente, explica cómo usarla y distingue qué ha comprobado y qué requiere preparación adicional. El agente que abra el repositorio debe poder identificar el propósito del proyecto, la estructura, los comandos de trabajo y los límites de sus cambios.

El producto no necesita generar la aplicación de negocio completa. Sí debe generar un punto de partida que funcione y evitar que el usuario tenga que reparar su configuración inicial.

## 2. Límites y relación con Agent Coordination

- **Agent Bootstrap es el producto que mejoramos en este repositorio.** Se conserva el paquete `agent-bootstrap` y sus comandos `projboot` y `agent-bootstrap`.
- **Agent Coordination es el método de desarrollo**: asignaciones, envío explícito, evidencia y aceptación del coordinador. Su interfaz es otra iniciativa y no se implementa en este plan.
- El canal inicial del producto sigue siendo su CLI. No se añade una interfaz gráfica a Bootstrap por inferencia.
- Adoptar repositorios existentes, sincronizar configuraciones durante meses y migrar proyectos quedan fuera de esta entrega. Podrán evaluarse después; no desplazan el flujo de creación.
- No se construye una plataforma de ejecución de agentes, un marketplace ni un generador de aplicaciones mediante un modelo.

## 3. Revisión de la implementación actual

Revisados README, especificación original, composición, perfiles y adaptadores del checkout local. El motor existente es una base aprovechable: resuelve perfiles, compone archivos y escribe el resultado. No hace falta reescribirlo.

La especificación original todavía describe nombres antiguos de comandos, una ruta personal para Graphify y un flujo de Git que no coincide plenamente con el código. Se conservará como documento histórico; al implementar se actualizará la documentación normativa a partir de este alcance.

Las carencias de producto más importantes son:

1. **Contexto poco accionable:** las instrucciones explican carpetas y arquitectura, pero no proporcionan consistentemente comandos reales para instalar, ejecutar, probar y construir.
2. **Perfiles que describen más de lo que entregan:** elegir arquitectura cambia principalmente el texto; llamar microservicio a un programa de saludo crea expectativas que la plantilla no cumple.
3. **Artefactos inconsistentes o inválidos:** los fallos observados en Helm, TypeScript, Ruby, metadatos, rutas y adaptadores afectan directamente al primer uso.
4. **Integraciones que se confunden con capacidades activadas:** crear una carpeta de memoria no instala un sistema de memoria; crear un marcador de Graphify no implica que exista un grafo ni su herramienta.
5. **Sin un contrato claro de finalización:** escribir archivos no demuestra que el proyecto instale, ejecute o pase pruebas.

## 4. Experiencia objetivo

1. **Elegir:** nombre, directorio de destino, perfil de proyecto, agentes y opciones de trabajo.
2. **Previsualizar:** archivos y directorios finales, herramientas requeridas e integraciones seleccionadas, sin escribir ni ejecutar procesos.
3. **Generar:** validar entradas y rutas, componer una configuración única y escribir un proyecto completo de forma segura.
4. **Preparar:** inicializar Git si se seleccionó y crear/conectar GitHub solo con una opción explícita.
5. **Comprobar:** analizar formatos y referencias locales; ejecutar verificaciones que instalen dependencias o usen herramientas externas únicamente cuando se hayan solicitado.
6. **Comenzar:** mostrar ruta, comandos iniciales, agentes configurados y resultados de comprobación con pendientes concretos.

El modo de creación local no necesita credenciales ni llamadas de red. Las instalaciones, comprobaciones con red y operaciones remotas son pasos explícitos, no efectos ocultos de una vista previa.

## 5. Contrato del proyecto generado

| Área | Resultado necesario |
|---|---|
| Base técnica | Código inicial ejecutable, metadatos válidos y dependencias coherentes con el perfil |
| Trabajo diario | Comandos documentados y comprobables para preparar, ejecutar, probar y construir cuando correspondan |
| Contexto compartido | `AGENTS.md` con propósito, estructura real, comandos y límites del proyecto |
| Agentes seleccionados | Adaptadores válidos que remitan al contexto común y usen formatos documentados |
| Convenciones | Rutas elegidas, instrucciones de cambios, pruebas y tratamiento de información sensible |
| Skills | Skills de proyecto seleccionadas o de ejemplo claramente identificadas, con referencias existentes |
| Memoria | Archivos iniciales explícitos y editables; sin prometer persistencia automática entre herramientas |
| Prompts | Un pequeño catálogo útil para comprender el proyecto, implementar un cambio y verificarlo |
| Higiene | Exclusiones de Git y Docker apropiadas, sin copiar credenciales o configuración personal real |
| Comprobaciones | Informe que distinga aprobado, fallido y no ejecutado, con razones y próximos pasos |

Las instrucciones para agentes deben corresponder al proyecto real. No deben citar comandos inexistentes, herramientas no seleccionadas ni carpetas que no se generan. Las reglas escritas orientan el comportamiento; no equivalen a controles técnicos de permisos.

## 6. Diseño mínimo

Mantener la separación actual entre perfiles, composición, adaptadores y CLI. Introducir una especificación resuelta del proyecto únicamente para datos que varios componentes necesitan compartir: identidad, perfil, rutas, agentes, integraciones y comandos de trabajo. Evitar duplicar esos hechos en instrucciones independientes.

La composición produce primero un plan completo de archivos. Después se validan las rutas renderizadas y normalizadas, los conflictos y los formatos. La vista previa y la escritura deben consumir ese mismo resultado. Así lo que se muestra coincide con lo que se crea.

La primera versión soportará un perfil Python modular completo como referencia. Mantener las plantillas existentes durante las correcciones, pero publicar su nivel de soporte con honestidad: un layout experimental no es un servicio verificado. No retirar comandos o plantillas existentes silenciosamente.

Las arquitecturas adicionales se implementarán como estructura y convenciones concretas cuando se aborde cada perfil. Hasta entonces, `--arch` se documenta como preferencia de instrucciones y no como arquitectura creada o validada.

Graphify, memoria personalizada y coordinación se tratan como opciones de perfil. Para no romper invocaciones existentes, cualquier cambio en valores predeterminados se hará explícito en la documentación y notas de versión. Un perfil de coordinación podrá incluir RULES, asignaciones, inbox/outbox y STATUS como plantillas; eso no ejecuta ni supervisa agentes.

## 7. Entregas y criterios de aceptación

### Entrega A — generación segura y coherente

Responsabilidad: `bootstrapper/cli.py`, `composer.py`, `presets.py` y pruebas correspondientes.

- Separar identidad de proyecto, destino y nombres técnicos cuando las restricciones difieran.
- Corregir el tratamiento de comillas, barras y saltos de línea en formatos estructurados.
- Detectar colisiones después de renderizar y normalizar rutas, además de conflictos archivo/directorio y escapes mediante enlaces.
- Validar todas las entradas antes de escribir. Para proyectos nuevos, usar preparación temporal y publicar el resultado completo; documentar límites de recuperación ante fallos de disco y operaciones externas.
- Rechazar opciones inválidas con mensajes claros; preservar cambios ajenos.

**Aceptación:** descripciones con comillas generan metadatos válidos; `./README.md` no sobrescribe silenciosamente README; un archivo llamado `src` no deja una generación parcialmente escrita por un conflicto detectable; entradas inválidas no crean archivos ni repositorios remotos.

### Entrega B — una base técnica que arranca

Responsabilidad: `bootstrapper/templates.py`, pruebas de plantillas e integración y documentación de perfiles.

- Reparar el chart Helm: whitespace de helpers, tag de imagen y renderizado de recursos.
- Reparar TypeScript: modelo de módulos y resolución coherentes, exclusiones y flujo de build real.
- Corregir nombres Ruby inválidos y documentar o completar las limitaciones de arranque Rails.
- Completar el perfil Python de referencia: instalación, código inicial, prueba útil, construcción y README de primeros pasos.
- Evitar instalar una segunda aplicación ficticia o añadir funcionalidades de negocio para demostrar el perfil.

**Aceptación:** desde el paquete instalado y fuera del checkout, generar cada perfil soportado y ejecutar su comprobación nativa. Python instala, ejecuta y pasa sus pruebas; TypeScript instala, compila y arranca; Helm pasa lint/render. Rails se presenta con su nivel de verificación real. No confundir renderizado Helm con despliegue exitoso.

### Entrega C — un agente puede trabajar desde la primera sesión

Responsabilidad: `bootstrapper/agents.py`, `presets.py`, contexto compartido en composición y pruebas.

- Generar instrucciones con comandos, estructura y verificaciones reales del perfil.
- Corregir frontmatter Cursor y configuración Claude; validar formatos y documentar versiones comprobadas.
- Mantener un contexto común y adaptadores pequeños; evitar reglas contradictorias entre agentes.
- Resolver archivos de memoria/skills personalizados sin referencias rotas ni copias de secretos.
- Componer integraciones condicionalmente; no borrar líneas arbitrarias que contienen la palabra Graphify.
- Retirar rutas absolutas de la máquina del autor.

**Aceptación:** todas las referencias locales generadas existen; desactivar una integración no deja instrucciones obligatorias sobre ella ni altera contenido personalizado ajeno; los formatos pasan sus validadores. Registrar por separado la verificación estática y la comprobación en clientes reales.

### Entrega D — previsualizar y comenzar con claridad

Responsabilidad: CLI, plan de composición, validación y README.

- Añadir una vista previa sin efectos secundarios y selección clara de perfil/opciones a través de la CLI existente.
- Mostrar el árbol final, requisitos y pasos que se ejecutarán.
- Ofrecer comprobaciones posteriores explícitas y un resumen útil de primeros pasos.
- Diferenciar archivos generados, herramientas configuradas y verificaciones ejecutadas.

**Aceptación:** la vista previa no escribe archivos, no inicializa Git, no invoca Graphify y no accede a GitHub. El árbol mostrado corresponde a lo generado con las mismas entradas. Un requisito ausente aparece como pendiente o fallo, nunca como éxito.

### Entrega E — GitHub y distribución confiables

Responsabilidad: `github_utils.py`, hooks Git, `.github/workflows/`, metadatos y pruebas de distribución.

- Usar una única historia Git autoritativa, evitando commits raíz independientes en local y remoto.
- Evitar subidas archivo por archivo y staging de archivos ajenos al plan generado.
- Informar fallos y estado parcial de operaciones externas sin afirmar que el checkout está listo.
- Añadir CI de cambios y gates de publicación con pruebas reales de artefactos generados.
- Probar wheel/sdist fuera del checkout, alinear versión/tag y actualizar metadatos obsoletos.
- Preparar Trusted Publishing; su activación depende de configurar la relación de confianza en PyPI/GitHub, y se verificará como paso externo aparte.

**Aceptación:** una prueba con remoto Git local demuestra historia compartida y primer push normal; fallos de preparación bloquean un resultado de éxito; una plantilla rota bloquea la publicación. Credenciales y operaciones GitHub reales requieren el entorno correspondiente, sin simular éxito si falta.

## 8. Ejecución con el método de coordinación

Convertir cada entrega en asignaciones pequeñas, comenzando por un fallo reproducible y su prueba. No despachar toda una entrega amplia a un trabajador sin límites de archivos y criterios concretos.

El coordinador mantiene reglas, asignaciones, dependencias y estado. Cada trabajador recibe su responsabilidad, escribe evidencia y limitaciones en outbox y solicita revisión por inbox. El coordinador inspecciona cambios y pruebas antes de aceptar. La persona conversa con el coordinador; no transmite prompts manualmente.

Orden: A → B → C → D → E. Las reparaciones urgentes de B pueden adelantarse como parches independientes si no dependen de la especificación compartida. No añadir UI de coordinación, frameworks o ejecución autónoma dentro de estas asignaciones.

Antes de implementar: preservar el `uv.lock` no rastreado y cualquier nuevo cambio ajeno, registrar la base Git y usar un entorno de trabajo adecuado. No publicar ni fusionar como consecuencia automática de completar una asignación.

## 9. Qué cambia respecto al plan anterior

- El centro pasa de mantener configuraciones a **comenzar un proyecto funcional con agentes**.
- El diferenciador buscado pasa de cantidad de adaptadores a **coherencia entre proyecto, comandos e instrucciones**.
- La validación sigue siendo esencial, pero sirve al flujo de bootstrap; no se convierte primero en otro producto de auditoría de repositorios.
- Adopción, sincronización y actualizaciones se posponen.
- El método de coordinación organiza nuestro trabajo; no redefine el propósito de Bootstrap.

## 10. Definición de terminado

Una persona instala el paquete publicado, genera un proyecto soportado, sigue los primeros pasos y abre su agente seleccionado. El proyecto funciona según su perfil y el agente recibe información precisa para trabajar. Los pasos que no se pudieron comprobar se muestran explícitamente. El usuario no necesita reparar archivos generados para comenzar.

La nueva promesa propuesta es: **«Crea un proyecto listo para desarrollar con agentes: estructura, herramientas y contexto trabajando juntos».**

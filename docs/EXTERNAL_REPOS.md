# Guia de operaciones - repositorios externos

Estos repos **no forman parte de `descarga`**: no se clonaron desde aqui, no
comparten historia y **no se modifican automaticamente**. Este documento
contiene los comandos exactos para operar cada uno **a mano**, en su propia
carpeta.

> Regla: **ningun `push` sin haber revisado antes el diff**. Todo comando
> destructivo (`stash`, `clean`, `reset`) tiene aqui su comando de
> recuperacion.

Estado verificado el **2026-10-21**.

---

## 1. `D:\Proyectos\Web\app tarija`

**Remoto:** `https://github.com/adrianpalacios782-dotcom/app-tarija.git`
**Estado:** rama `main`, **2 commits por delante** de `origin/main`
(`ahead 2`), working tree limpio salvo dos rutas sin trackear.

| Commit | Mensaje |
|---|---|
| `16709fc` | `docs: fuentes de datos v2 (octubre 2026) y auditoria tecnica (v1 historica)` |
| `1670cf8` | `feat(v2): frontend sobre el esquema v2 de venues + buscador por presupuesto` |

Sin trackear: `assets/`, `test_mirrors.cjs`. Sin stashes.

### 1.1 Inspeccionar los 2 commits adelantados

```powershell
cd "D:\Proyectos\Web\app tarija"

# Que commits NO estan todavia en GitHub
git log --oneline origin/main..HEAD

# Que cambios lleva cada uno (nivel de commit)
git show --stat 1670cf8
git show --stat 16709fc

# Diff completo de los 2 commits frente al remoto
git diff origin/main..HEAD --stat
git diff origin/main..HEAD

# Verificacion de que no hay divergencia con el remoto
git fetch origin
git log --oneline --left-right origin/main...HEAD
```

`git log --left-right origin/main...HEAD` es la comprobacion clave:
- `<` = commits que SOLO estan en `origin/main` (el remoto tiene trabajo que
  tu no tienes),
- `>` = commits que SOLO estan en tu rama (lo que vas a subir).

Si no aparece ninguna linea `<`, el push es directo (fast-forward) y no hay
riesgo de sobrescribir trabajo remoto.

### 1.2 Respaldar antes de publicar (stash con etiqueta)

```powershell
git add -A
git stash push -m "respaldo-pre-push-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
git stash list
```

Esto guarda **tracked modificados + untracked** (`assets/`,
`test_mirrors.cjs`) en un stash con nombre.

Recuperar (si hiciste el stash por error):

```powershell
git stash pop            # aplica y borra el stash
# o, si quieres conservar el stash:
git stash apply stash@{0}
```

### 1.3 Publicar los 2 commits (push seguro)

```powershell
# Push normal: solo sube los 2 commits, NO los untracked
git push origin main

# Verificacion: debe quedar "main...origin/main" sin "ahead"
git status -sb
git log --oneline -3
```

Un `git push` **no** sube `assets/` ni `test_mirrors.cjs` porque no estan
trackeados. Si lo que se quiere es publicarlos:

```powershell
git add assets test_mirrors.cjs
git commit -m "chore: assets del frontend v2 y test_mirrors"
git push origin main
```

### 1.4 Si el push es rechazado (remote'avance)

```powershell
git fetch origin
git rebase origin/main       # reaplica tus 2 commits encima del remoto
git push origin main

# O, si el rebase genera conflictos, se aborta sin perder nada:
# git rebase --abort
```

### 1.5 Si los untracked no se quieren

```powershell
git clean -nd      # dry run: muestra QUE se borraria
git clean -fd      # borra (NO recuperable: por eso el stash de 1.2 va antes)
```

### 1.6 Respaldo en rama propia (si el trabajo esta a medias)

```powershell
git switch -c wip/app-tarija-$(Get-Date -Format 'yyyyMMdd')
git add -A
git commit -m "wip: respaldo de trabajo en curso"
git push -u origin wip/app-tarija-$(Get-Date -Format 'yyyyMMdd')
```

---

## 2. `D:\Proyectos\Web\peponna\pepokita`

**Remoto:** `https://github.com/adrianpalacios782-dotcom/autolavado`
**Estado:** `main` **sincronizado** con `origin/main`, **8 archivos
modificados** sin commitear + **1 archivo sin trackear**.

```
 M server/api/reservations/cancel.post.ts
 M server/api/reservations/lookup.post.ts
 M server/utils/rate-limit.ts
 M shared/constants/index.ts
 M shared/schemas/reservation.ts
 M tests/constants.spec.ts
 M tests/rate-limit.spec.ts
 M tests/reservation-schemas.spec.ts
?? supabase/migrations/0009_code_entropy.sql
```

Resumen del diff: **8 archivos, 150 inserciones, 17 eliminaciones**. Sin
stashes.

### 2.1 Ver el diff de los 8 archivos modificados

```powershell
cd "D:\Proyectos\Web\peponna\pepokita"

# Solo el resumen (fichero y numero de lineas)
git diff --stat

# El diff completo, pagina a pagina
git diff

# Un archivo concreto
git diff server/utils/rate-limit.ts

# El archivo sin trackear (git diff NO lo muestra: hay que leerlo a mano)
Get-Content supabase/migrations/0009_code_entropy.sql
```

Atajo: `git diff --stat` + `git diff -U3` para no perder contexto, o
`git diff --color=always | less` en un terminal con paginador.

### 2.2 Guardar temporalmente con `git stash` (sin tocar el arbol de trabajo)

```powershell
# Respaldar y limpiar el working tree de una vez:
#   - los 8 archivos modificados vuelven a su version de HEAD
#   - el archivo sin trackear queda tambien guardado (con -u)
git add -A
git stash push -u -m "wip: code entropy + rate-limit ($(Get-Date -Format 'yyyyMMdd-HHmmss'))"

# Ver que hay en el stash
git stash list
git stash show --stat stash@{0}
```

> `-u` es lo que hace falta: sin el, `supabase/migrations/0009_code_entropy.sql`
> se queda en disco (untracked) y el stash solo recoge los modificados.

**Restaurar** (deshace el stash, dejando el arbol de trabajo como estaba):

```powershell
git stash pop             # aplica el stash y lo elimina de la lista
git stash apply stash@{0} # lo aplica pero lo CONSERVA en la lista
```

**Alternativa sin tocar el arbol de trabajo** (solo por si se quiere tener el
cambio en un parche en disco, sin mover nada del repo):

```powershell
git diff > "D:\Proyectos\Python\_backups\pepokita-$(Get-Date -Format 'yyyyMMdd-HHmmss').patch"
```

### 2.3 Commit local (no publicar todavia) - la opcion mas segura

```powershell
git add -A
git commit -m "feat(reservations): code entropy en migraciones y rate-limit"
git log --oneline -3

# Todavia NO se sube: el commit queda en local y es reversible con:
#   git reset --soft HEAD~1
```

### 2.4 Publicar cuando el trabajo este revisado

```powershell
git push origin main
```

### 2.5 Volver atras

```powershell
git reset --soft HEAD~1     # deshace el commit, conserva los cambios en el indice
git reset                   # deshace el commit, conserva los cambios en el working tree
```

---

## 3. Chequeo final

```powershell
# Estado resumido de los dos repos
git -C "D:\Proyectos\Web\app tarija" status -sb
git -C "D:\Proyectos\Web\peponna\pepokita" status -sb

# Stashes que se quedaron sin aplicar
git -C "D:\Proyectos\Web\app tarija" stash list
git -C "D:\Proyectos\Web\peponna\pepokita" stash list
```

> Los repos externos **no se tocan sin consultar**. Estos comandos existen para
> que los ejecute quien tenga el contexto del trabajo, no como paso automatico
> de ningun pipeline de este repositorio.

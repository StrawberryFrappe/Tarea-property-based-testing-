# Gestión de productos con Property-Based Testing

Sistema simple de gestión de **productos** (CRUD en memoria, sin interfaz gráfica)
cuyo comportamiento se valida con **pruebas basadas en propiedades** usando
[Hypothesis](https://hypothesis.readthedocs.io/) para Python.

## ¿Qué es Property-Based Testing?

En una prueba tradicional se escribe un ejemplo concreto y su resultado esperado:

```python
producto = repo.create(sku="ABC-1", name="Lápiz", price=Decimal("1.50"), stock=10)
assert repo.get(producto.id).name == "Lápiz"
```

En una prueba basada en propiedades se describe una **regla que debe cumplirse
para cualquier entrada válida**, y la librería genera automáticamente cientos de
entradas distintas intentando romperla:

```python
@given(data=product_data())
def test_get_returns_what_was_created(data):
    producto = repo.create(**data)
    assert repo.get(producto.id) == producto
```

Si Hypothesis encuentra una entrada que viola la propiedad, la **reduce
(shrinking)** hasta el contraejemplo más pequeño posible y lo muestra, lo que
facilita encontrar la causa del error.

## Dominio: `Product`

| Campo   | Tipo      | Reglas del dominio                                                    |
|---------|-----------|-----------------------------------------------------------------------|
| `id`    | `int`     | Asignado por el sistema, único, inmutable y **nunca se reutiliza**    |
| `sku`   | `str`     | Obligatorio, 1–32 caracteres (letras, dígitos y `-`), **único**       |
| `name`  | `str`     | No vacío ni sólo espacios, máximo 100 caracteres                      |
| `price` | `Decimal` | Finito, `>= 0`, máximo 2 decimales (no se aceptan `float`)            |
| `stock` | `int`     | Entero `>= 0` (no se aceptan `bool`)                                  |

### Operaciones (`ProductRepository`)

| Operación | Método                                   | Errores posibles                          |
|-----------|------------------------------------------|-------------------------------------------|
| Crear     | `create(sku, name, price, stock)`        | `ValidationError`, `DuplicateSkuError`    |
| Obtener   | `get(id)` / `list_all()`                 | `NotFoundError`                           |
| Actualizar| `update(id, *, sku=, name=, price=, stock=)` (parcial) | `NotFoundError`, `ValidationError`, `DuplicateSkuError` |
| Eliminar  | `delete(id)`                             | `NotFoundError`                           |

## Propiedades verificadas

Todas las pruebas están en [`tests/test_properties.py`](tests/test_properties.py).
Los generadores de datos (válidos e inválidos) están en
[`tests/strategies.py`](tests/strategies.py). Cada propiedad se ejecuta sobre
repositorios generados aleatoriamente, que ya contienen productos (algunos de
ellos eliminados, para que los ids no sean contiguos).

### Create

- **Crear agrega exactamente un producto con los datos dados**: para cualquier
  dato válido con SKU libre, el producto devuelto tiene esos datos, un id nuevo,
  se puede obtener con `get` y el listado crece en exactamente ese producto.
- **Los ids asignados son siempre distintos** para cualquier secuencia de creaciones.
- **Crear con datos inválidos se rechaza y no modifica nada**: si cualquier campo
  rompe una regla, se lanza `ValidationError` y el repositorio queda idéntico.
- **Crear con un SKU en uso se rechaza** con `DuplicateSkuError` sin modificar nada.

### Read

- **`get` devuelve exactamente lo que se creó**, para cualquier conjunto de productos.
- **`list_all` contiene todos los productos creados y nada más**, ordenados por id.
- **`get` de un id inexistente siempre falla** con `NotFoundError`.
- **Leer nunca modifica el repositorio**.

### Update

- **Actualizar cambia sólo los campos indicados del producto objetivo**: el id no
  cambia, los campos omitidos conservan su valor y el resto de los productos no se ve afectado.
- **Actualizar es idempotente**: aplicar la misma actualización dos veces produce
  el mismo resultado que aplicarla una vez.
- **Actualizar con datos inválidos se rechaza y no modifica nada**.
- **Actualizar al SKU de otro producto se rechaza** con `DuplicateSkuError`.
- **Actualizar un id inexistente siempre falla** con `NotFoundError`.

### Delete

- **Eliminar quita sólo el producto objetivo**: `get` falla después, el tamaño
  baja en 1 y los demás productos quedan intactos.
- **Eliminar dos veces el mismo producto falla** la segunda vez.
- **Eliminar un id inexistente siempre falla** sin modificar nada.
- **El SKU de un producto eliminado puede reutilizarse, pero su id no**.

### Prueba con estado (stateful)

[`tests/test_stateful.py`](tests/test_stateful.py) usa una
`RuleBasedStateMachine` de Hypothesis: genera **secuencias aleatorias** de
operaciones `create`, `get`, `update` y `delete` (incluyendo ids inexistentes y
SKUs repetidos) y, después de cada paso, compara el repositorio con un modelo
trivial (un `dict`). Además verifica en todo momento las invariantes:

- El contenido del repositorio coincide con el modelo.
- No existen dos productos con el mismo SKU.
- Ningún producto tiene precio o stock negativo.

## Estructura

```
src/inventory/
├── errors.py        # Excepciones del dominio
├── models.py        # Entidad Product y reglas de validación
└── repository.py    # ProductRepository (CRUD en memoria)
tests/
├── conftest.py      # Perfiles de Hypothesis
├── strategies.py    # Generadores de datos válidos e inválidos
├── test_properties.py
└── test_stateful.py
```

## Cómo ejecutar

Requiere Python 3.10 o superior.

```bash
python -m venv .venv
source .venv/bin/activate        # En Windows: .venv\Scripts\activate
pip install -e ".[test]"
pytest
```

Por defecto cada propiedad se prueba con 200 ejemplos generados. Para una
ejecución más exhaustiva (2000 ejemplos por propiedad):

```bash
HYPOTHESIS_PROFILE=thorough pytest
```

Para ver estadísticas de los datos generados:

```bash
pytest --hypothesis-show-statistics
```

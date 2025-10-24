Assets estáticos
=================

- logo-clinica.svg: Logo vectorial para el encabezado. Puedes reemplazarlo por tu archivo oficial.

Para usar un PNG/JPG en lugar del SVG, reemplaza la referencia en `templates/base.html`:

```jinja
<img src="{{ url_for('static', filename='logo-clinica.png') }}" ...>
```

por:

```jinja
<img src="{{ url_for('static', filename='logo-clinica.svg') }}" ...>
```

o simplemente coloca `logo-clinica.png` aquí y mantén la referencia actual.



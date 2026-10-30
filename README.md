@"
# De una carga a un motor: la fuerza de Lorentz simulada y demostrada
Simulador en Python (RK4) del movimiento de una partícula cargada en campos eléctricos y magnéticos, con modelo del motor homopolar.

Autores: Jhon Jairo Vera Acevedo, Anyelo Steven Sierra Monoga
Curso: Electromagnetismo. Universidad de Pamplona

## Cómo correrlo
pip install -r requirements.txt
python -m streamlit run simulador.py --theme.base dark
"@ | Set-Content README.md
git add README.md
git commit -m "Agregar README"
git push

# phelp
python help help programmer to find a function in a large package or similar function

case 1: I don't know where is train_test_split function located in sklearn
```python
import phelp
phelp.find_function("sklearn","train_test_split")
```
```output
{'package': 'sklearn',
 'function': 'train_test_split',
 'module': 'sklearn.model_selection._split',
 'file': '/usr/local/lib/python3.12/dist-packages/sklearn/model_selection/_split.py',
 'line': 2752}
```

if colab or kaggle import as following 
```python
!uv pip install git+https://github.com/chintu4/phelp
```
terminal

```bash
uv pip install git+https://github.com/chintu4/phelp
```
feel free to suggest changes or add new features :) 

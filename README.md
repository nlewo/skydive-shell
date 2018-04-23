#### A Shell to bring completion on Skydive Gremlin Queries


[![asciicast](https://asciinema.org/a/7ANDmKL4gzOiLD5QjVzG11MCn.png)](https://asciinema.org/a/7ANDmKL4gzOiLD5QjVzG11MCn)


It brings completions on 
- Skydive query steps: `limit`, `flows`, `count`,...
- `has` metadatas: keywords and values
- capture IDs

And several display modes
- `json`: raw output
- `pretty`: only general attributes are displayed

that can be set with the command `set format pretty`

#### Installation

```
pip install skydive-shell
```

or `python setup.py install`

#### Running tests
```
python setup.py test
```

#### Known Limitations... contributions are welcome!

- Some steps are missing
- Predicates (`within, ...`) are not supported
- Authentification is not supported by CLI options

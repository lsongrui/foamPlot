# foamplot

`foamplot` is a terminal plotting tool for foamLog-generated numeric files.

It reads the latest numeric values from one or more files and renders a live
terminal plot using `plotille`.

## Install

```bash
pipx install foamplot
```

## Usage

Run a demo:

```bash
foamplot --demo
```

Plot one file:

```bash
foamplot residuals.log
```

Plot several files:

```bash
foamplot p.log Ux.log Uy.log --names p,Ux,Uy
```

Follow files live:

```
foamplot p.log --follow
```

Use linear scale:

```bash
foamplot residuals.log --scale linear
```

Choose the numeric token from each line:

```bash
foamplot residuals.log --column 1
```

By default, foamplot uses the last numeric token on each line.

## Requirements
Python 3.8+
A Unicode-capable terminal
Unix-like system with tail

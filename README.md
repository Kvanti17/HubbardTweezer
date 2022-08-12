# DVR

![release](https://img.shields.io/github/v/release/Kvanti17/HubbardTweezer?color=green&include_prereleases)

Repo for DVR full/sparse diagonalizaiton using 3d `x,y,z`-reflection symmetry

## Features

1. Dynamics of on-off strobe potential
2. Solve Hubbard parameters of 2d arbitrary geometry
3. Equalize Hubbard parameters over all sites

## Dependencies

* [`pymanopt`](https://github.com/pymanopt/pymanopt) which dependes on [`torch`](https://github.com/pytorch/pytorch) (or [`autograd`](https://github.com/HIPS/autograd) by your preference)
* [`opt_einsum`](https://github.com/dgasmith/opt_einsum)
* [`graphviz`](https://github.com/xflr6/graphviz) and [`networkx`](https://github.com/networkx/networkx)
* `numpy`
* `scipy`
* `matplotlib`
* `pympler`
* `h5py`

## Modules

### DYR dynamics

* `DVR/core.py`: `DVR` base class to calculate DVR spectra
* `DVR/dynamics.py`: define `dynamics` class and `DVR_exe` function
* `DVR/output.py`: output storage `.h5` file interal structure definitions
* `DVR_exe.py`: execute script of DVR dynamics on command line

### Hubbard parameters

* The code now supports square/rectangular, Lieb, triangular, honeycomb and kagome lattices
* `Hubbard/core.py` : `MLWF` class to construct maximally localized Wannier funcitons
* `Hubbard/equalizer.py` : `HubbardParamEqualizer` class to equalize Hubbard parameters over all lattice sites
* `Hubbard/plot.py` and `Hubbard/graph.py` : `HubbardGraph` class to plot Hubbard parameters on lattice graphs, their difference is choice of graph plot packages
* `Hubbard_exe.py` : execute script to read inputs and write out Hubbard parameters for given lattice

### Test and executables

* `*.ipynb` are for test use. Most are self-explained by their title cells.


## TODO

* Test Hubbard parameter calculations for all lattice geometries
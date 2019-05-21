# meshplex

[![CircleCI](https://img.shields.io/circleci/project/github/nschloe/meshplex/master.svg)](https://circleci.com/gh/nschloe/meshplex/tree/master)
[![codecov](https://img.shields.io/codecov/c/github/nschloe/meshplex.svg)](https://codecov.io/gh/nschloe/meshplex)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![Documentation Status](https://readthedocs.org/projects/meshplex/badge/?version=latest)](https://readthedocs.org/projects/meshplex/?badge=latest)
[![PyPi Version](https://img.shields.io/pypi/v/meshplex.svg)](https://pypi.org/project/meshplex)
[![GitHub stars](https://img.shields.io/github/stars/nschloe/meshplex.svg?logo=github&label=Stars&logoColor=white)](https://github.com/nschloe/meshplex)

<p align="center">
  <img src="https://nschloe.github.io/meshplex/meshplex-logo.svg" width="20%">
</p>

Compute all sorts of interesting points, areas, and volumes in triangular and
tetrahedral meshes, with a focus on efficiency. Useful in many contexts, e.g.,
finite-element and finite-volume computations.

meshplex is used in [optimesh](https://github.com/nschloe/optimesh) and
[pyfvm](https://github.com/nschloe/pyfvm).

### Quickstart

```python
import numpy
import meshplex

# create a simple MeshTri instance
points = numpy.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
cells = numpy.array([[0, 1, 2]])
mesh = meshplex.MeshTri(points, cells)
# or read it from a file
# mesh = meshplex.read("pacman.vtk")

# triangle volumes
print(mesh.cell_volumes)

# circumcenters, centroids, incenters
print(mesh.cell_circumcenters)
print(mesh.cell_centroids)
print(mesh.cell_incenters)

# circumradius, inradius, cell quality, angles
print(mesh.cell_circumradius)
print(mesh.cell_inradius)
print(mesh.cell_quality)  # d * inradius / circumradius (min 0, max 1)
print(mesh.angles)

# control volumes, centroids
print(mesh.control_volumes)
print(mesh.control_volume_centroids)

# covolume/edge length ratios
print(mesh.ce_ratios)

# flip edges until the mesh is Delaunay
mesh.flip_until_delaunay()

# show the mesh
mesh.show()
```

meshplex works much the same way with tetrahedral meshes. For a documentation of all
classes and functions, see [readthedocs](https://meshplex.readthedocs.io/).

(For mesh creation, check out
[this list](https://github.com/nschloe/awesome-scientific-computing#meshing)).

### Plotting

#### Triangles
<img src="https://nschloe.github.io/meshplex/pacman.png" width="30%">

```python
import meshplex

mesh = meshplex.read("pacman-optimized.vtk")
mesh.show(
    # show_coedges=True,
    # control_volume_centroid_color=None,
    # mesh_color="k",
    # nondelaunay_edge_color=None,
    # boundary_edge_color=None,
    # comesh_color=(0.8, 0.8, 0.8),
    show_axes=False,
    )
```

#### Tetrahedra
<img src="https://nschloe.github.io/meshplex/tetrahedron.png" width="30%">

```python
import numpy
import meshplex

# Generate tetrahedron
node_coords = numpy.array(
    [
        [1.0, 0.0, -1.0 / numpy.sqrt(8)],
        [-0.5, +numpy.sqrt(3.0) / 2.0, -1.0 / numpy.sqrt(8)],
        [-0.5, -numpy.sqrt(3.0) / 2.0, -1.0 / numpy.sqrt(8)],
        [0.0, 0.0, numpy.sqrt(2.0) - 1.0 / numpy.sqrt(8)],
    ]
) / numpy.sqrt(3.0)
cells = [[0, 1, 2, 3]]

# Create mesh object
mesh = meshplex.MeshTetra(node_coords, cells)

# Plot cell 0 with control volume boundaries
mesh.show_cell(
    0,
    # barycenter_rgba=(1, 0, 0, 1.0),
    # circumcenter_rgba=(0.1, 0.1, 0.1, 1.0),
    # circumsphere_rgba=(0, 1, 0, 1.0),
    # incenter_rgba=(1, 0, 1, 1.0),
    # insphere_rgba=(1, 0, 1, 1.0),
    # face_circumcenter_rgba=(0, 0, 1, 1.0),
    control_volume_boundaries_rgba=(1.0, 0.0, 0.0, 1.0),
   line_width=3.0,
)
```

### Installation

meshplex is [available from the Python Package
Index](https://pypi.org/project/meshplex/), so simply type
```
pip3 install --user meshplex
```
to install.

### Testing

To run the meshplex unit tests, check out this repository and type
```
pytest
```

### License

meshplex is published under the [MIT license](https://en.wikipedia.org/wiki/MIT_License).

# -*- coding: utf-8 -*-
#
import numpy
from voropy.base import \
        _base_mesh, \
        _row_dot, \
        compute_tri_areas_and_ce_ratios, \
        compute_triangle_circumcenters

__all__ = ['MeshTetra']


def _my_dot(a, b):
    return numpy.einsum('ijk, ijk->ij', a, b)


class MeshTetra(_base_mesh):
    '''Class for handling tetrahedral meshes.

    .. inheritance-diagram:: MeshTetra
    '''
    def __init__(self, node_coords, cells, mode='geometric'):
        '''Initialization.
        '''
        # Assert that all vertices are used.
        # If there are vertices which do not appear in the cells list, this
        # ```
        # uvertices, uidx = numpy.unique(cells, return_inverse=True)
        # cells = uidx.reshape(cells.shape)
        # nodes = nodes[uvertices]
        # ```
        # helps.
        is_used = numpy.zeros(len(node_coords), dtype=bool)
        is_used[cells.flat] = True
        assert all(is_used)

        super(MeshTetra, self).__init__(node_coords, cells)

        self.cells = {
            'nodes': cells
            }

        self.create_cell_circumcenters_and_volumes()

        self._mode = mode
        self._ce_ratios = None
        self._control_volumes = None

        # Arrange the cell_face_nodes such that node k is opposite of face k in
        # each cell.
        nds = self.cells['nodes'].T
        self.node_face_cells = numpy.stack([
            nds[[1, 2, 3]],
            nds[[2, 3, 0]],
            nds[[3, 0, 1]],
            nds[[0, 1, 2]],
            ], axis=1)

        # Arrange the node_edge_face_cells such that node k is opposite of edge
        # k in each face.
        self.node_edge_face_cells = numpy.stack([
            numpy.stack([nds[[2, 3]], nds[[3, 1]], nds[[1, 2]]], axis=1),
            numpy.stack([nds[[3, 0]], nds[[0, 2]], nds[[2, 3]]], axis=1),
            numpy.stack([nds[[0, 1]], nds[[1, 3]], nds[[3, 0]]], axis=1),
            numpy.stack([nds[[1, 2]], nds[[2, 0]], nds[[0, 1]]], axis=1),
            ], axis=2)

        # create ei_dot_ei, ei_dot_ej
        self.edge_coords = \
            self.node_coords[self.node_edge_face_cells[1]] - \
            self.node_coords[self.node_edge_face_cells[0]]
        self.ei_dot_ei = numpy.einsum(
                'ijkl, ijkl->ijk',
                self.edge_coords,
                self.edge_coords
                )
        e_shift1 = self.edge_coords[[1, 2, 0]]
        e_shift2 = self.edge_coords[[2, 0, 1]]
        self.ei_dot_ej = numpy.einsum('ijkl, ijkl->ijk', e_shift1, e_shift2)

        return

    def get_ce_ratios(self):
        if self._ce_ratios is None:
            assert self._mode in ['geometric', 'algebraic']
            if self._mode == 'geometric':
                return self.compute_ce_ratios_geometric()
            else:  # 'algebraic'
                num_edges = len(self.edges['nodes'])
                self._ce_ratios = numpy.zeros(num_edges, dtype=float)
                raise RuntimeError('Disabled')
                idx, vals = self.compute_ce_ratios_algebraic()
                numpy.add.at(self._ce_ratios, idx, vals)
                self.circumcenter_face_distances = None
        return self._ce_ratios

    def mark_default_subdomains(self):
        self.subdomains = {}
        self.subdomains['everywhere'] = {
                'vertices': range(len(self.node_coords)),
                # 'edges': range(len(self.edges['nodes'])),
                'faces': range(len(self.faces['nodes']))
                }

        # Get vertices on the boundary faces
        boundary_faces = numpy.where(self.is_boundary_face)[0]
        boundary_vertices = numpy.unique(
                self.faces['nodes'][boundary_faces].flatten()
                )
        # boundary_edges = numpy.unique(
        #         self.faces['edges'][boundary_faces].flatten()
        #         )

        self.subdomains['boundary'] = {
                'vertices': boundary_vertices,
                # 'edges': boundary_edges,
                'faces': boundary_faces
                }

        return

    def create_cell_face_relationships(self):
        # All possible faces.
        # Face k is opposite of node k in each cell.
        # Make sure that the indices in each row are in ascending order. This
        # makes it easier to find unique rows
        nds = self.cells['nodes'].T
        a = numpy.hstack([
            nds[[1, 2, 3]],
            nds[[0, 2, 3]],
            nds[[0, 1, 3]],
            nds[[0, 1, 2]]
            ]).T

        # Find the unique faces
        # First sort...
        # TODO sort nds for less work
        a.sort(axis=1)
        # ... then find unique rows.
        b = numpy.ascontiguousarray(a).view(
                numpy.dtype((numpy.void, a.dtype.itemsize * a.shape[1]))
                )
        _, idx, inv, cts = numpy.unique(
                b,
                return_index=True,
                return_inverse=True,
                return_counts=True
                )
        face_nodes = a[idx]

        self.is_boundary_face = (cts == 1)

        self.faces = {
            'nodes': face_nodes
            }

        # cell->faces relationship
        num_cells = len(self.cells['nodes'])
        cells_faces = inv.reshape([4, num_cells]).T
        self.cells['faces'] = cells_faces

        # Store the opposing nodes too
        self.cells['opposing vertex'] = self.cells['nodes']

        # save for create_edge_cells
        self._inv_faces = inv

        return

    def create_face_edge_relationships(self):
        a = numpy.vstack([
            self.faces['nodes'][:, [1, 2]],
            self.faces['nodes'][:, [2, 0]],
            self.faces['nodes'][:, [0, 1]]
            ])

        # Find the unique edges
        b = numpy.ascontiguousarray(a).view(
                numpy.dtype((numpy.void, a.dtype.itemsize * a.shape[1]))
                )
        _, idx, inv = numpy.unique(
                b,
                return_index=True,
                return_inverse=True
                )
        edge_nodes = a[idx]

        self.edges = {
            'nodes': edge_nodes
            }

        # face->edge relationship
        num_faces = len(self.faces['nodes'])
        face_edges = inv.reshape([3, num_faces]).T
        self.faces['edges'] = face_edges

        return

    def create_cell_circumcenters_and_volumes(self):
        '''Computes the center of the circumsphere of each cell.
        '''
        cell_coords = self.node_coords[self.cells['nodes']]

        # This used to be
        # ```
        # a = cell_coords[:, 1, :] - cell_coords[:, 0, :]
        # b = cell_coords[:, 2, :] - cell_coords[:, 0, :]
        # c = cell_coords[:, 3, :] - cell_coords[:, 0, :]
        # a_cross_b = numpy.cross(a, b)
        # b_cross_c = numpy.cross(b, c)
        # c_cross_a = numpy.cross(c, a)
        # ```
        # The array X below unified a, b, c.
        X = cell_coords[:, [1, 2, 3], :] - cell_coords[:, [0], :]
        X_dot_X = numpy.einsum('ijk, ijk->ij', X, X)
        X_shift = cell_coords[:, [2, 3, 1], :] - cell_coords[:, [0], :]
        X_cross_Y = numpy.cross(X, X_shift)

        a = X[:, 0, :]
        a_dot_a = X_dot_X[:, 0]
        b_dot_b = X_dot_X[:, 1]
        c_dot_c = X_dot_X[:, 2]
        a_cross_b = X_cross_Y[:, 0, :]
        b_cross_c = X_cross_Y[:, 1, :]
        c_cross_a = X_cross_Y[:, 2, :]

        # Compute scalar triple product <a, b, c> = <b, c, a> = <c, a, b>.
        # The product is highly symmetric, so it's a little funny if there
        # should be no single einsum to compute it; see
        # <http://stackoverflow.com/q/42158228/353337>.
        omega = _row_dot(a, b_cross_c)

        self.cell_circumcenters = cell_coords[:, 0, :] + (
                b_cross_c * a_dot_a[:, None] +
                c_cross_a * b_dot_b[:, None] +
                a_cross_b * c_dot_c[:, None]
                ) / (2.0 * omega[:, None])

        # https://en.wikipedia.org/wiki/Tetrahedron#Volume
        self.cell_volumes = abs(omega) / 6.0
        return

# Question:
# We're looking for an explicit expression for the algebraic c/e ratios. Might
# it be that, analogous to the triangle dot product, the "triple product" has
# something to do with it?
# "triple product": Project one edge onto the plane spanned by the two others.
#
#     def compute_ce_ratios_algebraic(self):
#         # Precompute edges.
#         edges = \
#             self.node_coords[self.edges['nodes'][:, 1]] - \
#             self.node_coords[self.edges['nodes'][:, 0]]
#
#         # create cells -> edges
#         num_cells = len(self.cells['nodes'])
#         cells_edges = numpy.empty((num_cells, 6), dtype=int)
#         for cell_id, face_ids in enumerate(self.cells['faces']):
#             edges_set = set(self.faces['edges'][face_ids].flatten())
#             cells_edges[cell_id] = list(edges_set)
#
#         self.cells['edges'] = cells_edges
#
#         # Build the equation system:
#         # The equation
#         #
#         # |simplex| ||u||^2 = \sum_i \alpha_i <u,e_i> <e_i,u>
#         #
#         # has to hold for all vectors u in the plane spanned by the edges,
#         # particularly by the edges themselves.
#         cells_edges = edges[self.cells['edges']]
#         # <http://stackoverflow.com/a/38110345/353337>
#         A = numpy.einsum('ijk,ilk->ijl', cells_edges, cells_edges)
#         A = A**2
#
#         # Compute the RHS  cell_volume * <edge, edge>.
#         # The dot product <edge, edge> is also on the diagonals of A (before
#         # squaring), but simply computing it again is cheaper than extracting
#         # it from A.
#         edge_dot_edge = _row_dot(edges, edges)
#         rhs = edge_dot_edge[self.cells['edges']] \
#             * self.cell_volumes[..., None]
#
#         # Solve all k-by-k systems at once ("broadcast"). (`k` is the number
#         # of edges per simplex here.)
#         # If the matrix A is (close to) singular if and only if the cell is
#         # (close to being) degenerate. Hence, it has volume 0, and so all the
#         # edge coefficients are 0, too. Hence, do nothing.
#         sol = numpy.linalg.solve(A, rhs)
#
#         return self.cells['edges'], sol

    def compute_ce_ratios_geometric(self):

        face_areas, face_ce_ratios = \
            compute_tri_areas_and_ce_ratios(self.ei_dot_ej)

        # opposing nodes, faces
        v_op = self.cells['nodes'].T
        v = self.node_face_cells

        e0 = self.node_coords[v[0]] - self.node_coords[v_op]
        e1 = self.node_coords[v[1]] - self.node_coords[v_op]
        e2 = self.node_coords[v[2]] - self.node_coords[v_op]

        # This is the reference expression.
        # a = (
        #     2 * _my_dot(x0_cross_x1, x2)**2 -
        #     _my_dot(
        #         x0_cross_x1 + x1_cross_x2 + x2_cross_x0,
        #         x0_cross_x1 * x2_dot_x2[..., None] +
        #         x1_cross_x2 * x0_dot_x0[..., None] +
        #         x2_cross_x0 * x1_dot_x1[..., None]
        #     )) / (12.0 * face_areas)

        # Note that
        #
        #    6*tet_volume = abs(<x0 x x1, x2>)
        #                 = abs(<x1 x x2, x0>)
        #                 = abs(<x2 x x0, x1>).
        #
        # Also,
        #
        #    <a x b, c x d> = <a, c> <b, d> - <a, d> <b, c>.
        #
        # All those dot products can probably be cleaned up good.
        # TODO simplify
        # TODO can those perhaps be expressed as dot products of x_ - x_, i.e.,
        #      edges of the considered face
        e0_dot_e0 = _my_dot(e0, e0)
        e1_dot_e1 = _my_dot(e1, e1)
        e2_dot_e2 = _my_dot(e2, e2)
        e0_dot_e1 = _my_dot(e0, e1)
        e1_dot_e2 = _my_dot(e1, e2)
        e2_dot_e0 = _my_dot(e2, e0)

        delta = (
            # - alpha * x2_dot_x2
            e0_dot_e0 * e1_dot_e1 * e2_dot_e2 - e2_dot_e2 * e0_dot_e1**2 +
            e0_dot_e1 * e1_dot_e2 * e2_dot_e2 - e2_dot_e2 * e1_dot_e1 * e2_dot_e0 +
            e2_dot_e0 * e0_dot_e1 * e2_dot_e2 - e2_dot_e2 * e1_dot_e2 * e0_dot_e0 +
            #
            # - beta * x0_dot_x0
            e0_dot_e1 * e1_dot_e2 * e0_dot_e0 - e0_dot_e0 * e2_dot_e0 * e1_dot_e1 +
            e1_dot_e1 * e2_dot_e2 * e0_dot_e0 - e0_dot_e0 * e1_dot_e2**2 +
            e1_dot_e2 * e2_dot_e0 * e0_dot_e0 - e0_dot_e0 * e2_dot_e2 * e0_dot_e1 +
            #
            # - gamma * x1_dot_x1
            e2_dot_e0 * e0_dot_e1 * e1_dot_e1 - e1_dot_e1 * e0_dot_e0 * e1_dot_e2 +
            e1_dot_e2 * e2_dot_e0 * e1_dot_e1 - e1_dot_e1 * e0_dot_e1 * e2_dot_e2 +
            e0_dot_e0 * e2_dot_e2 * e1_dot_e1 - e1_dot_e1 * e2_dot_e0**2
            )

        a = (72.0 * self.cell_volumes[None]**2 - delta) / (12.0 * face_areas)

        # Distances of the cell circumcenter to the faces.
        # (shape: 4 x num_cells)
        self.circumcenter_face_distances = 0.5 * a / self.cell_volumes[None]

        # Multiply
        s = 0.5 * face_ce_ratios * self.circumcenter_face_distances[None]

        return s

    def get_cell_circumcenters(self):
        return self.cell_circumcenters

    def get_control_volumes(self):
        '''Compute the control volumes of all nodes in the mesh.
        '''
        if self._control_volumes is None:
            #   1/3. * (0.5 * edge_length) * covolume
            # = 1/6 * edge_length**2 * ce_ratio_edge_ratio
            ce = self.compute_ce_ratios_geometric()
            v = self.ei_dot_ei * ce / 6.0
            # TODO explicitly sum up contributions per cell first
            vals = numpy.array([v, v])
            idx = self.node_edge_face_cells
            self._control_volumes = \
                numpy.zeros(len(self.node_coords), dtype=float)
            numpy.add.at(self._control_volumes, idx, vals)
        return self._control_volumes

    def num_delaunay_violations(self):
        # Delaunay violations are present exactly on the interior faces where
        # the sum of the signed distances between face circumcenter and
        # tetrahedron circumcenter is negative.
        if self.circumcenter_face_distances is None:
            self.compute_ce_ratios_geometric()

        if 'faces' not in self.cells:
            self.create_cell_face_relationships()

        sums = numpy.zeros(len(self.faces['nodes']))
        numpy.add.at(
                sums,
                self.cells['faces'].T,
                self.circumcenter_face_distances
                )

        return numpy.sum(sums < 0.0)

    def show(self):
        from mpl_toolkits.mplot3d import Axes3D
        from matplotlib import pyplot as plt

        fig = plt.figure()
        ax = fig.gca(projection='3d')
        plt.axis('equal')

        X = self.node_coords
        for cell_id in range(len(self.cells['nodes'])):
            cc = self.cell_circumcenters[cell_id]
            #
            x = X[self.node_face_cells[..., [cell_id]]]
            face_ccs = compute_triangle_circumcenters(
                    x, self.ei_dot_ei, self.ei_dot_ej
                    )
            # draw the face circumcenters
            ax.plot(face_ccs[..., 0], face_ccs[..., 1], face_ccs[..., 2], 'go')
            # draw the connections
            #   tet circumcenter---face circumcenter
            for face_cc in face_ccs:
                ax.plot(
                    [cc[..., 0], face_cc[..., 0]],
                    [cc[..., 1], face_cc[..., 1]],
                    [cc[..., 2], face_cc[..., 2]],
                    'b-'
                    )
        return

    def show_edge(self, edge_id):
        '''Displays edge with ce_ratio.

        :param edge_id: Edge ID for which to show the ce_ratio.
        :type edge_id: int
        '''
        from mpl_toolkits.mplot3d import Axes3D
        from matplotlib import pyplot as plt

        if 'faces' not in self.cells:
            self.create_cell_face_relationships()
        if 'edges' not in self.faces:
            self.create_face_edge_relationships()

        fig = plt.figure()
        ax = fig.gca(projection='3d')
        plt.axis('equal')

        # find all faces with this edge
        adj_face_ids = numpy.where(
            (self.faces['edges'] == edge_id).any(axis=1)
            )[0]
        # find all cells with the faces
        # <http://stackoverflow.com/a/38481969/353337>
        adj_cell_ids = numpy.where(numpy.in1d(
            self.cells['faces'], adj_face_ids
            ).reshape(self.cells['faces'].shape).any(axis=1)
            )[0]

        # plot all those adjacent cells; first collect all edges
        adj_edge_ids = numpy.unique([
            adj_edge_id
            for adj_cell_id in adj_cell_ids
            for face_id in self.cells['faces'][adj_cell_id]
            for adj_edge_id in self.faces['edges'][face_id]
            ])
        col = 'k'
        for adj_edge_id in adj_edge_ids:
            x = self.node_coords[self.edges['nodes'][adj_edge_id]]
            ax.plot(x[:, 0], x[:, 1], x[:, 2], col)

        # make clear which is edge_id
        x = self.node_coords[self.edges['nodes'][edge_id]]
        ax.plot(x[:, 0], x[:, 1], x[:, 2], color=col, linewidth=3.0)

        # connect the face circumcenters with the corresponding cell
        # circumcenters
        X = self.node_coords
        for cell_id in adj_cell_ids:
            cc = self.cell_circumcenters[cell_id]
            #
            x = X[self.node_face_cells[..., [cell_id]]]
            face_ccs = compute_triangle_circumcenters(
                    x, self.ei_dot_ei, self.ei_dot_ej
                    )
            # draw the face circumcenters
            ax.plot(face_ccs[..., 0], face_ccs[..., 1], face_ccs[..., 2], 'go')
            # draw the connections
            #   tet circumcenter---face circumcenter
            for face_cc in face_ccs:
                ax.plot(
                    [cc[..., 0], face_cc[..., 0]],
                    [cc[..., 1], face_cc[..., 1]],
                    [cc[..., 2], face_cc[..., 2]],
                    'b-'
                    )

        # draw the cell circumcenters
        cc = self.cell_circumcenters[adj_cell_ids]
        ax.plot(cc[:, 0], cc[:, 1], cc[:, 2], 'ro')
        return

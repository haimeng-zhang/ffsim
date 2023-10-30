# (C) Copyright IBM 2023.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Test Wick's theorem utilities."""

import numpy as np
import pytest
import scipy.linalg
import scipy.sparse.linalg

import ffsim
from ffsim.states.wick import expectation_one_body_power, expectation_one_body_product


@pytest.mark.parametrize(
    "norb, occupied_orbitals",
    [
        (4, ([0, 1], [0, 1])),
        (3, ([0], [1, 2])),
        (2, ([], [0])),
    ],
)
def test_expectation_product(norb: int, occupied_orbitals: tuple[list[int], list[int]]):
    """Test expectation product."""
    occ_a, occ_b = occupied_orbitals
    nelec = len(occ_a), len(occ_b)
    dim = ffsim.dim(norb, nelec)

    rng = np.random.default_rng()

    # generate random one-body tensors
    n_tensors = 6
    one_body_tensors = []
    linops = []
    for _ in range(n_tensors):
        one_body_tensor = rng.standard_normal((norb, norb)).astype(complex)
        one_body_tensor += 1j * rng.standard_normal((norb, norb))
        linop = ffsim.contract.one_body_linop(one_body_tensor, norb=norb, nelec=nelec)
        one_body_tensors.append(one_body_tensor)
        linops.append(linop)

    # generate a random Slater determinant
    orbital_rotation = ffsim.random.random_unitary(norb, seed=rng)
    # TODO test spin-summed
    one_rdm = ffsim.slater_determinant_rdm(
        norb,
        occupied_orbitals,
        orbital_rotation=orbital_rotation,
        spin_summed=False,
    )

    # get the full statevector
    state = ffsim.slater_determinant(
        norb, occupied_orbitals, orbital_rotation=orbital_rotation
    )

    product_op = scipy.sparse.linalg.LinearOperator(
        shape=(dim, dim), matvec=lambda x: x
    )
    for i in range(n_tensors):
        product_op = product_op @ linops[i]
        computed = expectation_one_body_product(one_rdm, one_body_tensors[: i + 1])
        target = np.vdot(state, product_op @ state)
        np.testing.assert_allclose(computed, target, atol=1e-8)


def test_expectation_power():
    """Test expectation power."""
    norb = 5
    nelec = (3, 1)
    n_alpha, n_beta = nelec
    dim = ffsim.dim(norb, nelec)
    rng = np.random.default_rng()

    # generate a random one-body tensor
    one_body_tensor = rng.standard_normal((norb, norb)).astype(complex)
    one_body_tensor += 1j * rng.standard_normal((norb, norb))
    linop = ffsim.contract.one_body_linop(one_body_tensor, norb=norb, nelec=nelec)

    # generate a random Slater determinant
    vecs = ffsim.random.random_unitary(norb, seed=rng)
    occupied_orbitals_a = vecs[:, :n_alpha]
    occupied_orbitals_b = vecs[:, :n_beta]
    one_rdm_a = occupied_orbitals_a.conj() @ occupied_orbitals_a.T
    one_rdm_b = occupied_orbitals_b.conj() @ occupied_orbitals_b.T
    one_rdm = scipy.linalg.block_diag(one_rdm_a, one_rdm_b)

    # get the full statevector
    state = ffsim.slater_determinant(norb, (range(n_alpha), range(n_beta)))
    state = ffsim.apply_orbital_rotation(state, vecs, norb=norb, nelec=nelec)

    powered_op = scipy.sparse.linalg.LinearOperator(
        shape=(dim, dim), matvec=lambda x: x
    )
    expanded_one_body_tensor = scipy.linalg.block_diag(one_body_tensor, one_body_tensor)
    for power in range(7):
        computed = expectation_one_body_power(one_rdm, expanded_one_body_tensor, power)
        target = np.vdot(state, powered_op @ state)
        np.testing.assert_allclose(computed, target, atol=1e-8)
        powered_op = powered_op @ linop

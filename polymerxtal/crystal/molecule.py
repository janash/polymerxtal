"""
Functions for calculating molecule properties.
"""
import numpy as np

from polymerxtal.data import atomic_weights
from .measure import calculate_distance


class Molecule:
    def __init__(self, name, charge, symbols):
        self.name = name
        self.charge = charge
        self.symbols = symbols
        self.num_atoms = len(symbols)

    @property
    def symbols(self):
        return self._symbols

    @symbols.setter
    def symbols(self, symbols):
        self._symbols = symbols
        self.num_atoms = len(symbols)

    def __str__(self):
        return f'name: {self.name}\ncharge: {self.charge}\nsymbols: {self.symbols}'


def build_bond_list(coordinates, max_bond=1.55, min_bond=0):
    """Calculate bonds in a molecule base on a distance criteria.

    The pairwise distance between atoms is computed. If it is in the range 
    `min_bond` to `max_bond`, the atoms are counted as bonded.

    Parameters
    ----------
    coordinates : array-like
        The coordinates of the atoms.
    max_bond : float (optional)
        The maximum distance for two points to be considered bonded. The default
        is 1.5
    min_bond : float (optional)
        The minimum distance for two points to be considered bonded. The default
        is 0.
    
    Returns
    -------
    bonds : dict
        A dictionary where the keys are tuples of the bonded atom indices, and the
        associated values are the bond length.

    """

    if min_bond < 0 or max_bond < 0:
        raise ValueError('Min bond and max bond must be greater than 0')

    if len(coordinates) < 1:
        raise ValueError("Bond list can not be calculated for coordinate length less than 1.")

    # Find the bonds in a molecule
    bonds = {}
    num_atoms = len(coordinates)

    for atom1 in range(num_atoms):
        for atom2 in range(atom1 + 1, num_atoms):
            distance = calculate_distance(coordinates[atom1], coordinates[atom2])
            if distance > min_bond and distance < max_bond:
                bonds[(atom1, atom2)] = distance

    return bonds


def calculate_molecular_mass(symbols):
    """Calculate the mass of a molecule.
    
    Parameters
    ----------
    symbols : list
        A list of elements.
    
    Returns
    -------
    mass : float
        The mass of the molecule
    """

    mass = 0
    for atom in symbols:
        mass += atomic_weights[atom]

    return mass


def calculate_center_of_mass(symbols, coordinates):
    """Calculate the center of mass of a molecule.
    
    The center of mass is weighted by each atom's weight.
    
    Parameters
    ----------
    symbols : list
        A list of elements for the molecule
    coordinates : np.ndarray
        The coordinates of the molecule.
    
    Returns
    -------
    center_of_mass: np.ndarray
        The center of mass of the molecule.

    Notes
    -----
    The center of mass is calculated with the formula
    
    .. math:: \\vec{R}=\\frac{1}{M} \\sum_{i=1}^{n} m_{i}\\vec{r_{}i}
    
    """

    total_mass = calculate_molecular_mass(symbols)

    mass_array = np.zeros([len(symbols), 1])

    for i in range(len(symbols)):
        mass_array[i] = atomic_weights[symbols[i]]

    center_of_mass = sum(coordinates * mass_array) / total_mass

    return center_of_mass
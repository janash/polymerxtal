"""
This module is for functions Chain class.
"""

import numpy as np
import os, random

from polymerxtal.io import *
from polymerxtal.polymod import readPDB
from polymerxtal.struct2lammps import Create_Data_File
from polymerxtal.visualize import ovito_view

from polymerxtal.crystal.helice import Helice
from polymerxtal.crystal.infinite import (
    create_infinite_chain,
    correct_infinite_chain_position,
)
from polymerxtal.crystal.monomer import PolymerType, polymer_types
from polymerxtal.crystal.move import Sphere, Cluster, Translator, Rotator
from polymerxtal.crystal.unit import chain_periodicity


def calculate_rotation(vk):
    z = np.array([0, 0, 1])
    axis = np.cross(vk, z)
    theta = np.arccos(np.dot(z, vk))
    return axis, theta


def correct_chain_orientation(holder, num_monomers):
    unit, unit_distance, vk = chain_periodicity(holder, num_monomers)
    chain_cluster = Cluster()

    for atom in holder.pos:
        chain_cluster.add_particle(Sphere(holder.pos[atom]))

    axis, theta = calculate_rotation(vk)

    rotator = Rotator()
    chain_cluster.move(rotator, axis=axis, theta=theta)

    for i in range(holder.num_atoms):
        holder.pos[i] = chain_cluster.particles[i].center

    return holder, unit_distance


def get_mininum_position(positions):
    x = []
    y = []
    z = []
    for a_id in positions:
        x.append(positions[a_id][0])
        y.append(positions[a_id][1])
        z.append(positions[a_id][2])
    return np.array([min(x), min(y), min(z)])


def correct_chain_position(holder):
    mini_array = get_mininum_position(holder.pos)
    chain_cluster = Cluster()

    for atom in holder.pos:
        chain_cluster.add_particle(Sphere(holder.pos[atom]))

    translator = Translator()
    chain_cluster.move(translator, array=-mini_array)

    for i in range(holder.num_atoms):
        holder.pos[i] = chain_cluster.particles[i].center

    return holder


def get_maximum_position(positions):
    x = []
    y = []
    z = []
    for a_id in positions:
        x.append(positions[a_id][0])
        y.append(positions[a_id][1])
        z.append(positions[a_id][2])
    return np.array([max(x), max(y), max(z)])


class Chain:
    def __init__(self, **kwargs):
        """polymerxtal.crystal.chain.Chain class contains all the information about the polymer chain

        Parameters
        ----------
        polymer_type : str (optional)
            Current support polymer types include:
                PAN - Polyacrylonitrile
                PE - Polyethylene
                PP - Polypropylene
                PS - Polystyrene
                POM - Polyoxymethylene
                PTFE - Polytetrafluoroethylene
                PVC - Polyvinyl chloride
        helice : Helice class (optional)
            Current support helicities include:
                Helice(2,3,1)
                Helice(2,2,1)
                Helice(2,1,1) - Planar zig-zag
        num_monomers : int (optional)
            Number of monomers
        tacticity : str (optional)
            Tacticity of the polymer chain. Current support tacticities include: isotactic, atactic, syndiotactic
        chiriality : str (optional)
            Chiriality of the polymer chain. Current support chirialities include: left, right
        head_tail_defect_ratio : float (optional)
            Ratio of head-to-head and tail-to-tail connections
        configs : int (optional)
            Number of attempts to find a defect configuration
        infinite : bool (optional)
            Whether to create periodic infinite chain

        """

        polymer_type = "PE"
        helice = Helice()
        num_monomers = 30
        tacticity = ""
        chiriality = ""
        head_tail_defect_ratio = 0
        configs = 30
        infinite = False

        for key in kwargs:
            if key == "polymer_type":
                polymer_type = kwargs["polymer_type"]
            elif key == "helice":
                helice = kwargs["helice"]
            elif key == "num_monomers":
                num_monomers = kwargs["num_monomers"]
            elif key == "tacticity":
                tacticity = kwargs["tacticity"]
            elif key == "chiriality":
                chiriality = kwargs["chiriality"]
            elif key == "head_tail_defect_ratio":
                head_tail_defect_ratio = kwargs["head_tail_defect_ratio"]
            elif key == "configs":
                configs = kwargs["configs"]
            elif key == "infinite":
                infinite = kwargs["infinite"]
            else:
                raise KeyError(
                    "Unknown input %s for Chain class\n Please see help for more information"
                    % key
                )

        if "num_monomers" not in kwargs:
            if infinite:
                if helice.atoms * helice.motifs > 2:
                    num_monomers = helice.motifs
                else:
                    num_monomers = 2

        if polymer_type not in polymer_types:
            raise ValueError(
                polymer_type
                + " do not exist in our library, please consider using custom feature"
            )

        if not 0 <= (head_tail_defect_ratio) <= 1:
            raise ValueError(
                "Defect ratio of head to head and tail to tail connections is",
                head_tail_defect_ratio,
                "and should be in the range of [0,1]",
            )

        if num_monomers < helice.motifs:
            raise ValueError(
                "Number of monomers should be equal or larger than %d in order to generate Helice_%s chain.\nCurrent number of monomers is %d"
                % (helice.motifs, helice, num_monomers)
            )

        if infinite:
            if num_monomers % helice.motifs:
                raise ValueError(
                    "Number of monomers should be multiple of %d in order to generate infinite periodic Helice_%s chain.\nCurrent number of monomers is %d"
                    % (helice.motifs, helice, num_monomers)
                )
            elif num_monomers * helice.atoms < 3:
                raise ValueError(
                    "Number of backbone atoms should be more than 2 in order to create infinite periodic chain.\nCurrent number of backbone atoms along the periodic chain is %d\nPlease increate number of monomers."
                    % (num_monomers * helice.atoms)
                )

        self.polymer_type = polymer_types[polymer_type]
        self.helice = helice
        if len(self.polymer_type.backbone_atoms) != self.helice.atoms:
            raise ValueError("Number of backbone_atoms must be %d" % self.helice.atoms)

        self.num_monomers = num_monomers + 2 if infinite else num_monomers
        self.tacticity = tacticity
        if self.tacticity:
            if self.tacticity == "N/A":
                self.tacticity = ""
            elif self.tacticity not in ["isotactic", "atactic", "syndiotactic"]:
                raise TypeError(
                    "Unknown tacticity, please specify one of the following: isotactic, atactic and syndiotactic"
                )
            elif not self.polymer_type.backbone_atoms:
                raise ValueError("Please specify side_atom")

        self.chiriality = chiriality
        if str(self.helice) == str(Helice(2, 3, 1)):
            if self.chiriality == "left":
                self.torsions = {180, 300}
            elif self.chiriality == "right":
                self.torsions = {60, 180}
            else:
                raise ValueError("Please specify chiriality: left or right")
        elif str(self.helice) == str(Helice(2, 2, 1)):
            if self.chiriality == "left":
                self.torsions = {300}
            elif self.chiriality == "right":
                self.torsions = {60}
            else:
                raise ValueError("Please specify chiriality: left or right")
        elif str(self.helice) == str(Helice(2, 1, 1)):
            self.torsions = {180}
            if self.chiriality:
                self.chiriality = ""
                print("Zig-zag conformation does not have chiriality")

        self.head_tail_defect_ratio = head_tail_defect_ratio
        self.configs = configs
        self.infinite = infinite
        self.pattern = 0
        self.monomers = []
        self.weights = {}

    @property
    def polymer_type(self):
        return self._polymer_type

    @polymer_type.setter
    def polymer_type(self, polymer_type):
        if hasattr(self, "_polymer_type"):
            if str(self._polymer_type) != str(polymer_type):
                self._polymer_type = polymer_type
                self.built = 0
        else:
            self._polymer_type = polymer_type
            self.built = 0

    @property
    def helice(self):
        return self._helice

    @helice.setter
    def helice(self, helice):
        if hasattr(self, "_helice"):
            if str(self._helice) != str(helice):
                self._helice = helice
                self.built = 0
        else:
            self._helice = helice
            self.built = 0

    @property
    def num_monomers(self):
        return self._num_monomers

    @num_monomers.setter
    def num_monomers(self, num_monomers):
        if hasattr(self, "_num_monomers"):
            if self._num_monomers != num_monomers:
                self._num_monomers = num_monomers
                self.built = 0
        else:
            self._num_monomers = num_monomers
            self.built = 0

    @property
    def tacticity(self):
        return self._tacticity

    @tacticity.setter
    def tacticity(self, tacticity):
        if hasattr(self, "_tacticity"):
            if self._tacticity != tacticity:
                self._tacticity = tacticity
                self.built = 0
        else:
            self._tacticity = tacticity
            self.built = 0

    @property
    def chiriality(self):
        return self._chiriality

    @chiriality.setter
    def chiriality(self, chiriality):
        if hasattr(self, "_chiriality"):
            if self._chiriality != chiriality:
                self._chiriality = chiriality
                self.built = 0
        else:
            self._chiriality = chiriality
            self.built = 0

    @property
    def head_tail_defect_ratio(self):
        return self._head_tail_defect_ratio

    @head_tail_defect_ratio.setter
    def head_tail_defect_ratio(self, head_tail_defect_ratio):
        if hasattr(self, "_head_tail_defect_ratio"):
            if self._head_tail_defect_ratio != head_tail_defect_ratio:
                self._head_tail_defect_ratio = head_tail_defect_ratio
                self.built = 0
        else:
            self._head_tail_defect_ratio = head_tail_defect_ratio
            self.built = 0

    @property
    def configs(self):
        return self._configs

    @configs.setter
    def configs(self, configs):
        if hasattr(self, "_configs"):
            if self._configs != configs:
                self._configs = configs
                self.built = 0
        else:
            self._configs = configs
            self.built = 0

    @property
    def infinite(self):
        return self._infinite

    @infinite.setter
    def infinite(self, infinite):
        if hasattr(self, "_infinite"):
            if self._infinite != infinite:
                self._infinite = infinite
                self.built = 0
        else:
            self._infinite = infinite
            self.built = 0

    def find_configurations(self, find_inverse_path=False):

        if self.head_tail_defect_ratio:
            find_inverse_path = True
        self.backbones = self.polymer_type.identify_backbone_path(
            find_inverse_path=find_inverse_path
        )

        monomers = {}
        monomer_index = []

        for key in self.backbones:
            m = self.backbones[key].name.split("T")
            if m[0] not in monomers:
                monomers[m[0]] = []
                monomer_index.append(m[0])
            for T in [60, 180, 300]:
                m_name = self.backbones[key].name + "T" + str(T)
                key_torsions = {eval(m[1]), T}
                if self.torsions == key_torsions:
                    monomers[m[0]].append(m_name)

        self.configurations = {}
        config_index = 1

        if find_inverse_path:
            self.pattern = 0
            while config_index <= self.configs:
                sequence = random.choices(
                    [0, 1],
                    [1 - self.head_tail_defect_ratio, self.head_tail_defect_ratio],
                    k=self.num_monomers - 1,
                )
                if self.tacticity == "isotactic" or (not self.tacticity):
                    m = random.choice(monomer_index)
                    m_name = random.choice(monomers[m])
                    h_t_label = m_name[0]
                    tor_label = m_name[m_name.index("T") :]
                    self.configurations[config_index] = [m_name]
                    for seq in sequence:
                        if seq:
                            m = random.choice(monomer_index)
                            m_name = random.choice(monomers[m])
                            while not (
                                h_t_label != m_name[0]
                                and tor_label == m_name[m_name.index("T") :]
                            ):
                                m = random.choice(monomer_index)
                                m_name = random.choice(monomers[m])
                            h_t_label = m_name[0]
                        self.configurations[config_index].append(m_name)
                elif self.tacticity == "atactic" or self.tacticity == "syndiotactic":
                    m1 = random.choice(monomer_index)
                    m1_name = random.choice(monomers[m1])
                    h_t_label = m1_name[0]
                    tor_label = m1_name[m1_name.index("T") :]
                    m2 = random.choice(monomer_index)
                    m2_name = random.choice(monomers[m2])
                    while not (
                        h_t_label == m2_name[0]
                        and m1 != m2
                        and tor_label == m2_name[m2_name.index("T") :]
                    ):
                        m2 = random.choice(monomer_index)
                        m2_name = random.choice(monomers[m2])
                    if self.tacticity == "atactic":
                        self.configurations[config_index] = [
                            random.choice([m1_name, m2_name])
                        ]
                    elif self.tacticity == "syndiotactic":
                        self.configurations[config_index] = [m1_name]
                    for i, seq in enumerate(sequence):
                        if seq:
                            m1 = random.choice(monomer_index)
                            m1_name = random.choice(monomers[m1])
                            while not (
                                h_t_label != m1_name[0]
                                and tor_label == m1_name[m1_name.index("T") :]
                            ):
                                m1 = random.choice(monomer_index)
                                m1_name = random.choice(monomers[m1])
                            h_t_label = m1_name[0]
                            m2 = random.choice(monomer_index)
                            m2_name = random.choice(monomers[m2])
                            while not (
                                h_t_label == m2_name[0]
                                and m1 != m2
                                and tor_label == m2_name[m2_name.index("T") :]
                            ):
                                m2 = random.choice(monomer_index)
                                m2_name = random.choice(monomers[m2])
                        if self.tacticity == "atactic":
                            self.configurations[config_index].append(
                                random.choice([m1_name, m2_name])
                            )
                        elif self.tacticity == "syndiotactic":
                            if i % 2:
                                self.configurations[config_index].append(m1_name)
                            else:
                                self.configurations[config_index].append(m2_name)
                config_index += 1
        else:
            if self.tacticity == "isotactic" or (not self.tacticity):
                self.pattern = 0
                for m in monomer_index:
                    for m_name in monomers[m]:
                        self.configurations[config_index] = [m_name, m_name]
                        config_index += 1
            elif self.tacticity == "atactic" or self.tacticity == "syndiotactic":
                self.pattern = 1 if self.tacticity == "atactic" else 0
                for m1 in monomer_index:
                    for m1_name in monomers[m1]:
                        for m2 in monomer_index[monomer_index.index(m1) + 1 :]:
                            for m2_name in monomers[m2]:
                                if (
                                    m1_name[m1_name.index("T") :]
                                    == m2_name[m2_name.index("T") :]
                                ):
                                    self.configurations[config_index] = [
                                        m1_name,
                                        m2_name,
                                    ]
                                    config_index += 1

    def input_polymod(self, ofile, config_index):

        self.monomers = set(self.configurations[config_index])

        des = open(ofile, "w")
        des.write("\n")
        des.write("\n")
        des.write("bond_scale 1.2 \n")
        des.write("\n")
        des.write("temperature 300\n")
        des.write("\n")
        des.write("backbone_bond_length 1.5351\n")
        des.write("\n")
        des.write("bond_cutoff 4\n")
        des.write("\n")
        des.write("\n")

        for key in self.backbones:
            for T in [60, 180, 300]:
                m = self.backbones[key].name + "T" + str(T)
                if m in self.monomers:
                    des.write(
                        "monomer %s %s %d %d\n"
                        % (
                            m,
                            self.backbones[key].path,
                            self.backbones[key].head_index,
                            self.backbones[key].tail_index,
                        )
                    )
                    des.write("\n")
                    des.write("torsion 3 fixed %f\n" % T)
                    des.write(
                        "torsion 4 fixed %s\n" % self.backbones[key].name.split("T")[1]
                    )
                    des.write("\n")
        des.write("\n")
        des.write("\n")
        # with open(in_path, 'r') as file:  #with open('file.txt', 'r') as file:
        #    filedata = file.read()

        # Replace the target string
        # Replace the target string
        # filedata = filedata.replace('nc', str(nc))
        # filedata = filedata.replace('monomer_path', monomer_path)
        # filedata = filedata.replace('nm', str(num_monomers))
        # filedata = filedata.replace('lcx', str(cell[0]))
        # filedata = filedata.replace('lcy', str(cell[1]))
        # filedata = filedata.replace('lcz', str(cell[2]))
        # filedata = filedata.replace('ccx', str(cpos[0]))
        # filedata = filedata.replace('ccy', str(cpos[1]))
        # filedata = filedata.replace('ccz', str(cpos[2]))
        # filedata = filedata.replace('dx', str(caxis[0]))
        # filedata = filedata.replace('dy', str(caxis[1]))
        # filedata = filedata.replace('dz', str(caxis[2]))
        # filedata = filedata.replace('crad', str(radius))
        # filedata = filedata.replace('clc', str(lc + 200))
        # filedata = filedata.replace('irad', str(2 * radius - 5))
        # filedata = filedata.replace('mctemp', str(mctemp))

        if self.pattern:
            weight = 1 / len(self.monomers)
            for m in self.monomers:
                self.weights[m] = weight
            stereo_type = "weight " + str(len(self.monomers))
        else:
            stereo_type = "pattern " + str(len(self.configurations[config_index]))

        for m in self.configurations[config_index]:
            stereo_type += " " + m
            if self.pattern:
                stereo_type += " " + str(self.weights[m])
        # filedata = filedata.replace('stereo_type', stereo_type)
        des.write("stereo s1 %s\n" % stereo_type)
        des.write("\n")
        des.write("density 0.0001\n")
        des.write("\n")
        des.write("chains 1 #40\n")
        des.write("\n")
        des.write("\n")
        des.write("monomers %d\n" % self.num_monomers)
        des.write("\n")
        des.write("\n")
        des.write("\n")
        des.write("chain_stereo 1 s1 1.0\n")
        des.write("\n")
        des.write("grid_size 6.0\n")
        des.write("\n")
        des.write("sample monte_carlo\n")
        des.write("\n")
        des.write("configs 50\n")
        des.write("\n")
        des.write("energy LJ \n")
        des.write("\n")
        des.write("energy_cutoff 6.0\n")
        des.write("\n")
        des.write("\n")
        des.write("write unwrapped_pdb \n")
        des.write("\n")
        des.write("write intermediate\n")
        des.write("\n")
        des.write("\n")
        des.write("\n")
        des.write("\n")
        des.close()

        # Write the file out again
        # with open(ofile, 'w') as file:  #with open('run_file.txt', 'w') as file:
        #    file.write(filedata)

    def build_helix(self):
        self.find_configurations()

        print(
            "Total %d possible configurations found for Helice %s"
            % (len(self.configurations), self.helice)
        )

        config_success = 0
        for config_index in self.configurations:
            print("Try Configuration", config_index)

            # Build polymod input file
            self.input_polymod(".tmp/run_polymod.txt", config_index)
            # input_polymod('run_polymod.txt',monomer_path,helice,backbone_atoms=backbone_atoms,tacticity=tacticity,side_atom=side_atom,chiriality=chiriality,num_monomers=num_monomers)
            # input_polymod('run_polymod.txt',monomer_path, helice, tacticity, chiriality, num_monomers=num_monomers)

            # Run polymod
            run_polymod(".tmp/run_polymod.txt", validate_bond=True)
            if validate_coords(".tmp/chains_unwrapped.pdb", ".tmp/bonds.dat"):
                config_success = 1
                print("Success for Configuration", config_index)
                break
            else:
                print("Fail for Configuration", config_index)

        if config_success:
            return readPDB(".tmp/chains_unwrapped.pdb")
        else:
            raise Exception(
                "Unable to generate a successful Helice_%s configuration with %s due to unavoided overlap of atoms."
                % (self.helice, self.polymer_type.name)
            )

    def build_chain(self, **kwargs):
        """polymerxtal.crystal.chain.Chain.build_chain function builds a polymer chain with specified information

        Parameters
        ----------
        use_visualize : bool (optional)
            Whether to view chain structure
        create_lmpdata_file : bool (optional)
            Whether to create corresponding LAMMPS data file or not
        bondscale : float (optional)
            Bond scale applied to equilibrium bond lengths
        ffield : str (optional)
            Force field. Current support force field include: Dreiding, PCFF
        charge : str (optional)
            Charge equilibration method. Current support charge method include: Gasteiger
        create_lmpinput_file : bool (optional)
            Whether to create corresponding LAMMPS input File or not

        """
        # Build the path to the sample files.
        # in_path = os.path.join(current_location, '..', 'data', 'polymod_input', 'sample_chain.txt')
        # monomer_path = os.path.join(current_location, '..', 'data', 'pdb', 'monomer', 'PAN.pdb')

        # Build helix
        holder = self.build_helix()

        # Correct chain orientation
        holder, unit_distance = correct_chain_orientation(holder, self.num_monomers)

        # Create infinite periodic polymer helix chain
        if self.infinite:
            holder = create_infinite_chain(holder, self.num_monomers)

        # Correct chain position
        holder = correct_chain_position(holder)

        # Further correct chain position for infinite chain
        if self.infinite:
            holder = correct_infinite_chain_position(holder)

        helix_name = self.polymer_type.name + "_helix_%s%s%s%s%s" % (
            self.helice,
            "_" + self.tacticity[:3] if self.tacticity else "",
            "+"
            if self.chiriality == "right"
            else "-"
            if self.chiriality == "left"
            else "",
            "_custom" if self.head_tail_defect_ratio else "",
            "_inf" if self.infinite else "",
        )
        self.helix_name = helix_name
        write_pdb(helix_name + ".pdb", holder.el_names, holder.pos)

        self.built = 1
        self.holder = holder

        maxi_array = get_maximum_position(holder.pos)
        self.x = maxi_array[0]
        self.y = maxi_array[1]
        if self.infinite:
            self.z = unit_distance * (self.num_monomers - 2) / self.helice.motifs
        else:
            self.z = maxi_array[2]
        self.alpha = 90
        self.beta = 90
        self.gamma = 90

        use_visualize = False
        create_lmpdata_file = False
        bondscale = 1.1
        ffield = "Dreiding"
        charge = "Gasteiger"
        create_lmpinput_file = False

        for key in kwargs:
            if key == "use_visualize":
                use_visualize = kwargs["use_visualize"]
            elif key == "create_lmpdata_file":
                create_lmpdata_file = kwargs["create_lmpdata_file"]
            elif key == "bondscale":
                bondscale = kwargs["bondscale"]
            elif key == "ffield":
                ffield = kwargs["ffield"]
            elif key == "charge":
                charge = kwargs["charge"]
            elif key == "create_lmpinput_file":
                create_lmpinput_file = kwargs["create_lmpinput_file"]
            else:
                raise KeyError(
                    "Unknown input %s for build_chain function\n Please see help for more information"
                    % key
                )

        # Create LAMMPS data file
        if create_lmpdata_file:
            Create_Data_File(
                helix_name + ".pdb",
                bondscale=bondscale,
                ffield=ffield,
                charge=charge,
                xhi=self.x,
                yhi=self.y,
                zhi=self.z,
                alpha=self.alpha,
                beta=self.beta,
                gamma=self.gamma,
                outputName=helix_name,
            )

            # Create LAMMPS input file
            if create_lmpinput_file:
                write_lmp_ifile(
                    ffield=ffield,
                    datafile=helix_name + ".data",
                    potentialfile="X6paircoeffs.txt",
                )

        # View chain structure
        if use_visualize:
            write_pdb(
                helix_name + "_view.pdb", holder.el_names, holder.pos, connect=False
            )
            # if create_lmpdata_file:
            #    ovito_view(
            #        helix_name + ".data", helix_name + "_Front.png", view="Front"
            #    )
            #    ovito_view(helix_name + ".data", helix_name + "_Top.png", view="Top")
            # else:
            # write_pdb(f"{helix_name}_ovito.pdb", h.el_names, h.pos, connect=False)
            ovito_view(
                helix_name + "_view.pdb", helix_name + "_Front.png", view="Front"
            )
            ovito_view(helix_name + "_view.pdb", helix_name + "_Top.png", view="Top")

        return helix_name

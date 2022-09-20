from os import link
import numpy as np
import numpy.linalg as la
from numpy.linalg import LinAlgError
from numbers import Number
from typing import Iterable, Union
from scipy.optimize import minimize, least_squares, OptimizeResult
from configobj import ConfigObj
from time import time

from .core import *
from .output import *


def str_to_flags(target: str) -> tuple[bool, bool, bool, bool, bool, bool]:
    u, t, v = False, False, False
    fix_u, fix_t, fix_v = False, False, False
    if 'u' in target or 'U' in target:
        u = True
        if 'U' in target:
            # Whether to fix target in combined cost function
            fix_u = True
    if 't' in target or 'T' in target:
        t = True
        if 'T' in target:
            fix_t = True
    if 'v' in target or 'V' in target:
        v = True
        if 'V' in target:
            fix_v = True
    return u, t, v, fix_u, fix_t, fix_v


class HubbardEqualizer(MLWF):

    def __init__(
            self,
            N,
            equalize=False,  # Homogenize trap or not
            eqtarget='UvT',  # Equalization target
            scale_factor=None,  # Scale factor for cost function
            Ut: float = None,  # Interaction target in unit of tx
            method: str = 'trf',  # Minimize algorithm method
            nobounds: bool = False,  # Whether to use bounds or not
            waist='x',  # Waist to vary, None means no waist change
            random: bool = False,  # Random initial guess
            iofile=None,  # Input/output file
            write_log: bool = False,  # Whether to write detailed log into iofile
            x0: np.ndarray = None,  # Initial value for minimization to start from
            *args,
            **kwargs):
        super().__init__(N, *args, **kwargs)

        # set equalization label in file output
        self.eq_label = eqtarget
        self.waist_dir = waist
        self.eqinfo = {}
        self.log = write_log
        if isinstance(scale_factor, Number):
            self.sf = scale_factor
        else:
            print('Equalize: scale_factor is not a number. Set to None.')
            self.sf = None

        if equalize:
            if self.lattice_dim > 1 and self.waist_dir != None \
                    and self.waist_dir != 'xy':
                self.waist_dir = 'xy'

            method = 'Nelder-Mead' if method == 'NM' else method
            if not isinstance(x0, np.ndarray):
                print('Illegal x0 provided. Use no initial guess.')
                x0 = None

            self.equalize(target=eqtarget,
                          Ut=Ut, x0=x0,
                          random=random,
                          nobounds=nobounds,
                          method=method,
                          callback=False,
                          iofile=iofile)

    def equalize(self,
                 target: str = 'UvT',
                 Ut: float = None,  # Target onsite interaction in unit of tx
                 x0: np.ndarray = None,
                 weight: np.ndarray = np.ones(3),
                 random: bool = False,
                 nobounds: bool = False,
                 method: str = 'trf',
                 callback: bool = False,
                 iofile: ConfigObj = None
                 ) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:

        print(f"Equalize: varying waist direction: {self.waist_dir}.")
        print(f"Equalize: method: {method}")
        print(f"Equalize: quantities: {target}\n")
        u, t, v, fix_u, fix_t, fix_v = str_to_flags(target)
        links = self.xylinks()

        # Equalize trap depth first, to make sure
        self.equalize_trap_depth()
        print(f"Equalize: trap depths equalzlied to {self.Voff}.")

        res = self.singleband_Hubbard(u=u, offset=True, output_unitary=True)
        if u:
            A, U, V = res
        else:
            A, V = res
            U = None

        nnt = self.nn_tunneling(A)
        # Set tx, ty target to be small s.t.
        # lattice spacing is not too close and WF collapses
        txTarget, tyTarget = self.t_target(nnt, links, np.min)
        # Energy scale factor, set to be of avg initial tx
        if not isinstance(self.sf, Number):
            self.sf = np.min([txTarget, tyTarget]
                             ) if tyTarget != None else txTarget
        if not fix_t:
            txTarget, tyTarget = None, None

        if fix_u:
            if Ut is None:
                # Set target interaction to be max of initial interaction.
                # This is to make traps not that localized in the middle to equalize U.
                # As to achieve larger U traps depths seem more even.
                Utarget = np.max(U)
                Ut = Utarget / self.sf
            else:
                Utarget = Ut * self.sf
        else:
            Utarget = None

        # If V is shifted to zero then fix_v has no effect
        Vtarget = np.mean(np.real(np.diag(A))) if fix_v else None

        print(f'Equalize: scale factor: {self.sf}')
        print(f'Equalize: target tunneling: {txTarget, tyTarget}')
        print(f'Equalize: target interaction: {Utarget}')
        print(f'Equalize: target onsite potential: {Vtarget}')
        # Voff_bak = self.Voff
        # ls_bak = self.trap_centers
        # w_bak = self.waists

        v0, bounds = self.init_guess(
            random=random, nobounds=nobounds, lsq=True)

        if isinstance(x0, np.ndarray):
            try:
                if len(x0) == len(v0):
                    v0 = x0  # Use passed initial guess
            except:
                print("Equalize: external initial guess is not passed.")
                pass

        self.eqinfo = {'Nfeval': 0,
                       'cost': np.array([]).reshape(0, 3),
                       'ctot': np.array([]),
                       'fval': np.array([]),
                       'diff': np.array([]),
                       'x': np.array([]).reshape(0, *v0.shape)}

        # Decide if each step cost function used the last step's unitary matrix
        # callback can have sometimes very few iteraction steps
        # But since unitary optimize time cost is not large in larger systems
        # it is not recommended
        # Pack U0 to be mutable, thus can be updated in each iteration of minimize
        U0 = [V] if callback else None

        if method in ['trf', 'dogbox']:
            res = self._eq_lsq((u, t, v), links, (Vtarget, Utarget,
                               txTarget, tyTarget), (v0, bounds), weight, method, U0, iofile)
        elif method in ['Nelder-Mead', 'Powell', 'CG', 'BFGS', 'L-BFGS-B', 'TNC', 'COBYLA', 'SLSQP', 'trust-constr', 'dogleg', 'trust-ncg', 'trust-exact', 'trust-krylov']:
            res = self._eq_min((u, t, v), links, (Vtarget, Utarget,
                               txTarget, tyTarget), (v0, bounds), weight, method, U0, iofile)
        else:
            raise ValueError(
                f'Equalize: unknown optimization method: {method}. Please choose from trf, dogbox, Nelder-Mead, Powell, CG, BFGS, L-BFGS-B, TNC, COBYLA, SLSQP, trust-constr, dogleg, trust-ncg, trust-exact, trust-krylov')

        self._update_log_final(res)

        return self.param_unfold(res.x, 'final')

    def trap_mat(self):
        # depth of each trap center
        tc = np.zeros((self.Nsite, dim))
        vij = np.ones((self.Nsite, self.Nsite))
        for i in range(self.Nsite):
            tc[i, :] = np.append(self.trap_centers[i] * self.lc, 0)
            for j in range(i):
                vij[i, j] = -DVR.Vfun(self, *(tc[i] - tc[j]))
                vij[j, i] = vij[i, j]  # Potential is symmetric in distance
        return vij

    def equalize_trap_depth(self):
        vij = self.trap_mat()
        # Set trap depth target to be the deepest one
        Vtarget = np.max(vij @ np.ones(self.Nsite))
        try:
            # Equalize trap depth
            # Powered to compensate for trap unevenness
            self.Voff = la.solve(vij, Vtarget * np.ones(self.Nsite))**2
        except:
            raise LinAlgError('Homogenize: failed to solve for Voff.')

    def eff_dof(self):
        # Record all free DoFs in the function
        self.Voff_dof = np.ones(self.Nindep).astype(bool)

        if self.waist_dir == None:
            self.w_dof = None
        else:
            wx = np.tile('x' in self.waist_dir, self.Nindep)
            wy = np.tile('y' in self.waist_dir, self.Nindep)
            self.w_dof = np.array([wx, wy]).T.reshape(-1)

        tcx = np.array([not self.inv_coords[i, 0] for i in range(self.Nindep)])
        if self.lattice_dim == 1:
            tcy = np.tile(False, self.Nindep)
        else:
            tcy = np.array([not self.inv_coords[i, 1]
                           for i in range(self.Nindep)])
        self.tc_dof = np.array([tcx, tcy]).T.reshape(-1)

        return self.Voff_dof, self.w_dof, self.tc_dof

    def init_guess(self, random=False, nobounds=False, lsq=True) -> tuple[np.ndarray, tuple]:
        # Mark effective DoFs
        self.eff_dof()

        # Trap depth variation inital guess and bounds
        # s1 = np.inf if nobounds else 0.1
        # v01 = np.ones(self.Nindep)
        v01 = symm_fold(self.reflection, self.Voff)
        if nobounds:
            b1 = list((-np.inf, np.inf) for i in range(self.Nindep))
        else:
            b1 = list((0, np.inf) for i in range(self.Nindep))

        # Waist variation inital guess and bounds
        # UB from resolution limit; LB by wavelength
        if nobounds:
            s2 = (-np.inf, np.inf)
        else:
            s2 = (self.l / self.w, 1.2)
        if self.waist_dir == None:
            v02 = np.array([])
            b2 = []
        else:
            v02 = np.ones(2 * self.Nindep)
            if lsq:
                b2 = list(s2
                          for i in range(2 * self.Nindep) if self.w_dof[i])
                v02 = v02[self.w_dof]
            else:
                b2 = list(s2 if self.w_dof[i] else (
                    1, 1) for i in range(2 * self.Nindep))

        # Lattice spacing variation inital guess and bounds
        # Must be separated by at least 1 waist
        # TODO: make the bound to be xy specific
        if nobounds:
            s3 = (-np.inf, np.inf)
        else:
            s3 = (1 - 1 / self.lc[0]) / 2
        v03 = self.tc0[self.reflection[:, 0]].flatten()
        if lsq:
            b3 = list((v03[i] - s3, v03[i] + s3)
                      for i in range(2 * self.Nindep) if self.tc_dof[i])
            v03 = v03[self.tc_dof]
        else:
            b3 = list((v03[i] - s3, v03[i] + s3)
                      if self.tc_dof[i] else (0, 0) for i in range(2 * self.Nindep))

        bounds = tuple(b1 + b2 + b3)

        if random:
            v0 = np.array([np.random.uniform(b[0], b[1]) for b in bounds])
        else:
            v0 = np.concatenate((v01, v02, v03))

        self._set_trap_params(v0, self.verbosity or random, 'Intial')

        return v0, bounds

    def _set_trap_params(self, v0: np.ndarray, verb, status):
        trap_depth = v0[:self.Nindep]
        if self.waist_dir != None:
            trap_waist = np.ones((self.Nindep, 2))
            trap_waist[self.w_dof.reshape(
                self.Nindep, 2)] = v0[self.Nindep:np.sum(self.w_dof) + self.Nindep]
        else:
            trap_waist = None
        trap_center = np.zeros((self.Nindep, 2))
        trap_center[self.tc_dof.reshape(
            self.Nindep, 2)] = v0[-np.sum(self.tc_dof):]
        if verb:
            print(f"\nEqualize: {status} trap depths: {trap_depth}")
            if self.waist_dir != None:
                print(f"Equalize: {status} waists:")
                print(trap_waist)
            print(f"Equalize: {status} trap centers:")
            print(trap_center)
        return trap_depth, trap_waist, trap_center

    def param_unfold(self, point: np.ndarray, status: str = 'current'):
        td, tw, tc = self._set_trap_params(point, self.verbosity, status)
        self.symm_unfold(self.Voff, td)
        if self.waist_dir != None:
            self.symm_unfold(self.waists, tw)
        self.symm_unfold(self.trap_centers, tc, graph=True)
        self.update_lattice(self.trap_centers)
        return self.Voff, self.waists, self.trap_centers, self.eqinfo

    def cbd_func(self,
                 point: np.ndarray,
                 info: Union[dict, None],
                 links: tuple[np.ndarray, np.ndarray],
                 target: tuple[float, ...],
                 utv: tuple[bool] = (False, False, False),
                 scale_factor: float = None,
                 weight: np.ndarray = np.ones(3),
                 unitary: Union[list, None] = None,
                 mode: str = 'cost',
                 report: ConfigObj = None) -> float:
        self.param_unfold(point, 'current')

        # By accessing element of a list, x0 is mutable and can be updated
        if unitary != None and self.lattice_dim > 1:
            x0 = unitary[0]
        else:
            x0 = None

        u, t, v = utv

        res = self.singleband_Hubbard(
            u=u, x0=x0, offset=True, output_unitary=True)
        if u:
            A, U, x0 = res
        else:
            A, x0 = res
            U = None
        # x0 is used to update unitary[0] in the next iteration

        # Print out Hubbard parameters
        if self.verbosity > 1:
            print(f'scale_factor = {scale_factor}')
            print(f'V = {np.diag(A)}')
            print(f't = {abs(self.nn_tunneling(A))}')
            print(f'U = {U}')

        xlinks, ylinks = links
        Vtarget = None
        Utarget = None
        txTarget, tyTarget = None, None
        if isinstance(target, Iterable):
            Vtarget, Utarget, txTarget, tyTarget = target

        w = weight.copy()

        if mode == 'cost':
            return self._cost_func(point, info, scale_factor, report, (u, t, v), (A, U), (xlinks, ylinks), (Vtarget, Utarget, txTarget, tyTarget), w)
        elif mode == 'res':
            return self._res_func(point, info, scale_factor, report, (u, t, v), (A, U), (xlinks, ylinks), (Vtarget, Utarget, txTarget, tyTarget), w)
        else:
            raise ValueError(f"Equalize: mode {mode} not supported.")

    def _update_log(self, point, info, report, cvec, fval, io_freq=10):
        # Keep revcord
        if info != None:
            info['Nfeval'] += 1
            info['x'] = np.append(info['x'], point[None], axis=0)
            info['cost'] = np.append(info['cost'], cvec[None], axis=0)
            ctot = la.norm(cvec)
            info['ctot'] = np.append(info['ctot'], ctot)
            info['fval'] = np.append(info['fval'], fval)
            diff = info['fval'][len(info['fval'])//2] - fval
            info['diff'] = np.append(info['diff'], diff)
            # display information
            if info['Nfeval'] % io_freq == 0:
                if isinstance(report, ConfigObj):
                    info['sf'] = self.sf
                    info['success'] = False
                    info['exit_status'] = -1
                    info['termination_reason'] = "Not terminated yet"
                    write_equalization(
                        report, info, self.log, final=False)
                    write_trap_params(report, self)
                    write_singleband(report, self)
        if self.verbosity:
            print(f"Cost function by terms: {cvec}")
            print(f"Total cost function value fval={fval}\n")
            if info != None:
                print(
                    f'i={info["Nfeval"]}\tc={cvec}\tc_i={fval}\tc_i//2-c_i={diff}')

    def _update_log_final(self, res: OptimizeResult):
        self.eqinfo['sf'] = self.sf
        self.eqinfo['success'] = res.success
        self.eqinfo['exit_status'] = res.status
        self.eqinfo['termination_reason'] = res.message

# ================= GENERAL MINIMIZATION =================

    def _eq_min(self, utv, links, target, init_guess, weight, method, U0, iofile) -> OptimizeResult:
        u, t, v = utv
        xlinks, ylinks = links
        Vtarget, Utarget, txTarget, tyTarget = target
        v0, bounds = init_guess

        def cost_func(point: np.ndarray, info: Union[dict, None]) -> float:
            c = self.cbd_func(point, info, (xlinks, ylinks),
                              (Vtarget, Utarget, txTarget, tyTarget), (u, t, v), self.sf, weight, unitary=U0, mode='cost', report=iofile)
            return c

        t0 = time()
        # Method-specific options
        if method == 'Nelder-Mead':
            options = {
                'disp': True, 'return_all': True, 'adaptive': False, 'xatol': 1e-6, 'fatol': 1e-9, 'maxiter': 500 * self.Nindep}
        elif method == 'SLSQP':
            options = {'disp': True, 'ftol': np.finfo(float).eps}

        res = minimize(cost_func, v0, args=self.eqinfo,
                       bounds=bounds, method=method, options=options)
        t1 = time()
        print(f"Equalization took {t1 - t0} seconds.")
        return res

    def _cost_func(self, point, info, scale_factor, report, utv, res, links, target, w):
        u, t, v = utv
        xlinks, ylinks = links
        Vtarget, Utarget, txTarget, tyTarget = target
        A, U = res

        cu = 0
        if u:
            # U is different, as calculating U costs time
            cu = self.u_cost_func(U, Utarget, scale_factor)

        cv = self.v_cost_func(A, Vtarget, scale_factor)
        if not v:
            # Force V to have no effect on cost function
            w[2] = 0

        ct = self.t_cost_func(A, (xlinks, ylinks), (txTarget, tyTarget))
        if not t:
            # Force t to have no effect on cost function
            w[1] = 0

        cvec = np.array((cu, ct, cv))
        c = w @ cvec
        cvec = np.sqrt(cvec)
        fval = np.sqrt(c)
        self._update_log(point, info, report, cvec, fval)
        return c

    def v_cost_func(self, A, Vtarget: float, Vfactor: float = None) -> float:
        if Vtarget is None:
            Vtarget = np.mean(np.real(np.diag(A)))
        if Vfactor is None:
            Vfactor = abs(Vtarget)
            if Vfactor < 1e-2:  # Avoid division by zero
                Vfactor = 0.2
        cv = np.mean((np.real(np.diag(A)) - Vtarget)**2) / Vfactor**2
        if self.verbosity > 1:
            print(f'Onsite potential target={Vtarget}')
            print(f'Onsite potential cost cv={cv}')
        return cv

    def t_cost_func(self, A: np.ndarray, links: tuple[np.ndarray, np.ndarray],
                    target: tuple[float, ...]) -> float:
        links = self.xylinks() if links is None else links
        nnt = self.nn_tunneling(A)
        # Mostly not usable if not directly call this function
        if target is None:
            txTarget, tyTarget = self.t_target(nnt, links)
        elif isinstance(target, Iterable):
            txTarget, tyTarget = target
            if txTarget is None:
                txTarget, tyTarget = self.t_target(nnt, links)
        xlinks, ylinks = links

        ct = np.mean((abs(nnt[xlinks]) / txTarget - 1)**2)
        if tyTarget != None:
            ct += np.mean((abs(nnt[ylinks]) / tyTarget - 1)**2)
        if self.verbosity > 1:
            print(f'Tunneling target=({txTarget}, {tyTarget})')
            print(f'Tunneling cost ct={ct}')
        return ct

    def u_cost_func(self, U, Utarget: float, Ufactor: float = None) -> float:
        if Utarget is None:
            Utarget = np.mean(U)
        if Ufactor is None:
            Ufactor = Utarget
        cu = np.mean((U - Utarget)**2) / Ufactor**2
        if self.verbosity > 1:
            print(f'Onsite interaction target fixed to {Utarget}')
            print(f'Onsite interaction cost cu={cu}')
        return cu

# ==================== LEAST SQUARES ====================

    def _eq_lsq(self, utv, links, target, init_guess, weight, method, U0, iofile) -> OptimizeResult:
        u, t, v = utv
        xlinks, ylinks = links
        Vtarget, Utarget, txTarget, tyTarget = target
        v0, bounds = init_guess

        def res_func(point: np.ndarray, info: Union[dict, None]):
            c = self.cbd_func(point, info, (xlinks, ylinks),
                              (Vtarget, Utarget, txTarget, tyTarget), (u, t, v), self.sf, weight, unitary=U0, mode='res', report=iofile)
            return c

        # if nobounds:
        #     method = 'lm'
        #     print(f'Method is set to {method} given unconstraint problem.')

        # Convert to tuple of (lb, ub)
        ba = np.array(bounds)
        bounds = (ba[:, 0], ba[:, 1])

        t0 = time()
        res = least_squares(res_func, v0, bounds=bounds, args=(self.eqinfo,),
                            method=method, verbose=2,
                            xtol=1e-8, ftol=1e-8, gtol=1e-8, max_nfev=500 * self.Nindep)
        t1 = time()
        print(f"Equalization took {t1 - t0} seconds.")
        return res

    def _res_func(self, point, info, scale_factor, report, utv, res, links, target, w):
        u, t, v = utv
        xlinks, ylinks = links
        Vtarget, Utarget, txTarget, tyTarget = target
        A, U = res

        cu = np.zeros(self.Nsite)
        if u:
            # U is different, as calculating U costs time
            cu = self.u_res_func(U, Utarget, scale_factor)

        cv = self.v_res_func(A, Vtarget, scale_factor)
        if not v:
            # Force V to have no effect on cost function
            w[2] = 0

        ct = self.t_res_func(A, (xlinks, ylinks), (txTarget, tyTarget))
        if not t:
            # Force t to have no effect on cost function
            w[1] = 0

        cvec = np.array([la.norm(cu), la.norm(ct), la.norm(cv)])
        # Weighted cost function, weight is in front of each squared term
        c = np.concatenate(
            [np.sqrt(w[0]) * cu, np.sqrt(w[1]) * ct, np.sqrt(w[2]) * cv])
        # The cost func val in least_squares is fval**2 / 2
        fval = la.norm(c)
        self._update_log(point, info, report, cvec, fval)
        return c

    def v_res_func(self, A, Vtarget: float, Vfactor: float = None):
        if Vtarget is None:
            Vtarget = np.mean(np.real(np.diag(A)))
        if Vfactor is None:
            Vfactor = abs(Vtarget)
            if Vfactor < 1e-2:  # Avoid division by zero
                Vfactor = 0.2
        cv = (np.real(np.diag(A)) - Vtarget) / \
            (Vfactor * np.sqrt(len(A)))
        if self.verbosity > 2:
            print(f'Onsite potential target={Vtarget}')
            print(f'Onsite potential residue cv={cv}')
        return cv

    def t_res_func(self, A: np.ndarray, links: tuple[np.ndarray, np.ndarray],
                   target: tuple[float, ...]):
        nnt = self.nn_tunneling(A)
        # Mostly not usable if not directly call this function
        if target is None:
            xlinks, ylinks, txTarget, tyTarget = self.xylinks(nnt)
        elif isinstance(target, Iterable):
            xlinks, ylinks = links
            txTarget, tyTarget = target
            if txTarget is None:
                xlinks, ylinks, txTarget, tyTarget = self.xylinks(nnt)

        ct = (abs(nnt[xlinks]) - txTarget) / \
            (txTarget * np.sqrt(np.sum(xlinks)))
        if tyTarget != None:
            ct = np.concatenate(
                (ct, (abs(nnt[ylinks]) - tyTarget) / (tyTarget * np.sqrt(np.sum(ylinks)))))
        if self.verbosity > 2:
            print(f'Tunneling target=({txTarget}, {tyTarget})')
            print(f'Tunneling residue ct={ct}')
        return ct

    def u_res_func(self, U, Utarget: float, Ufactor: float = None):
        if Utarget is None:
            Utarget = np.mean(U)
        if Ufactor is None:
            Ufactor = Utarget
        cu = (U - Utarget) / (Ufactor * np.sqrt(len(U)))
        if self.verbosity > 2:
            print(f'Onsite interaction target fixed to {Utarget}')
            print(f'Onsite interaction residue cu={cu}')
        return cu

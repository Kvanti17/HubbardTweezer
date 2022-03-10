from re import M
from matplotlib.axes import Axes
import numpy as np
import matplotlib.pyplot as plt
from DVR_exe import *
from matplotlib import gridspec
import h5py
from scipy.optimize import curve_fit
from scipy.stats.mstats import gmean
import matplotlib as mpl
import matplotlib.colors as colors
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

mpl.rcParams['figure.dpi'] = 300


class plot(dynamics):
    def __init__(self,
                 cvg='N',
                 quantity='gs',
                 N=10,
                 R0: np.ndarray = 3 * np.array([1, 1, 2.4]),
                 freq_list: np.ndarray = np.arange(20, 200, 20),
                 time=(1000.0, 0),
                 avg=1,
                 dim=3,
                 smooth=(-1, 10),
                 model='Gaussian',
                 trap=(1.0452E2, 1E-6),
                 mem_eff=False,
                 wavefunc=False,
                 realtime=False,
                 symmetry=False,
                 absorber=False,
                 ab_param=(57.04, 1)) -> None:
        super().__init__(N, R0, freq_list, time, avg, dim, model, trap,
                         mem_eff, wavefunc, realtime, smooth, symmetry,
                         absorber, ab_param)
        self.cvg = cvg
        self.set_quantity(quantity)

    def set_quantity(self, quantity):
        self.quantity = quantity
        if self.quantity == 'gs':
            self.wavefunc = False
        elif self.quantity == 'trap':
            self.wavefunc = True

    def set_each_n(self, N_list, R0_list, i):
        self.update_N(N_list[i], R0_list[i])
        if self.cvg == 'N':
            self.cvg_str = '$R_0$={}w'.format(self.R0[:self.dim])
        elif self.cvg == 'R':
            self.cvg_str = 'dx={}w'.format(self.dx[:self.dim])
        self.n_list.append(self.n)
        self.dx_list.append(self.dx)
        # n_list, dx_list are mutable, no need to output
        np.set_printoptions(precision=2, suppress=True)
        if self.model == 'Gaussian':
            self.freq_unit_str = 'kHz'
            self.freq_unit = 1
            self.t_unit = 's'
            self.xlabel = 't/s'
        elif self.model == 'sho':
            self.freq_unit_str = '$\omega$'
            self.freq_unit = 1
            self.t_unit = ''
            self.xlabel = 't/$\omega^{-1}$'
        # return n_list, dx_list

    def set_all_n(self, N_list, R0_list, avg_no, avg):
        self.n_list = []
        self.dx_list = []
        for i in range(len(N_list)):
            self.set_each_n(N_list, R0_list, i)
            self.title1 = '{}D {:g}'.format(
                self.dim, avg_no / self.step_no * self.stop_time)
            self.title1 = self.title1 + self.t_unit
            self.title1 = self.title1 + ' moving-avged {} {} population \n'.format(
                self.model, self.quantity)
            final_str = 'w/ freq={:g}'.format(self.freq * self.freq_unit) + self.freq_unit_str \
                            + ' ' + self.cvg_str
            self.title1 = self.title1 + final_str
            self.title2 = '{}D {} {} population \n'.format(
                self.dim, self.model, self.quantity)
            self.title2 = self.title2 + final_str
            if not avg:
                self.title1 = self.title2
                self.title2 = None

    def filename_gen(self, N_list: list, R0_list: list, t_step, i: int):
        self.update_N(N_list[i], R0_list[i])
        return super().filename_gen(t_step)


def fit_fun(x, b, rvs_flg=False):
    if rvs_flg:
        return np.exp(-x * b)
    else:
        return np.exp(-x / b)


def avg_data(data, avg_no):
    rho_avg = np.array([])
    for m in range(data.shape[0]):
        rho_avg = moving_avg(data[:m + 1], rho_avg, avg_no)
    return rho_avg


def plot_dynamics(N_list,
                  R0_list,
                  dvr: plot,
                  length=1,
                  fig=None,
                  fit=True,
                  avg_no=100):

    if avg_no == 0:
        avg_no = 10
        figno = 1
        avg = False
    else:
        figno = 2
        avg = True
    first_fig = False
    if fig == None:
        fig = plt.figure(figsize=[6 * figno, 5 * dvr.freq_list_len])
        first_fig = True
        if dvr.freq_list_len == 1:
            ax_list = [fig.subplots(dvr.freq_list_len, figno, sharey=True)]
        else:
            ax_list = fig.subplots(dvr.freq_list_len, figno, sharey=True)
    else:
        ax_list = fig.axes

    N_list = list(N_list)

    for fi in range(dvr.freq_list_len):
        t_step = dvr.set_each_freq(fi)
        # set height ratios for subplots
        if figno == 1:
            axs = [ax_list[fi]]
        else:
            axs = ax_list[fi, :]

        dvr.set_all_n(N_list, R0_list, avg_no, avg)

        data = get_data(N_list, R0_list, dvr, t_step)
        plot_length = int(data[0].t.shape[0] / length)
        # final_val = np.array([])
        lifetime = np.array([])

        for i in range(len(N_list)):
            # final_val = moving_avg(data[i][1], final_val, 16 * avg_no)
            # if i == len(N_list)-1:
            #     np.set_printoptions(precision=6, suppress=False)
            #     print(data[i][1][:plot_length])
            if fit:
                lifetime, popt, rvs_flag = fit_tau(lifetime, data[i])
            if avg:
                rho_avg = avg_data(data[i].rho_gs, avg_no)
                axs[0].plot(data[i].t[:plot_length],
                            rho_avg[:plot_length][:, None],
                            label='$N_0$={}'.format(N_list[i]))
                axs[2].plot(data[i].t[:plot_length],
                            data[i].rho_gs[:plot_length],
                            label='$N_0$={}'.format(N_list[i]))
            else:
                axs[0].semilogy(
                    data[i].t[:plot_length],
                    data[i].rho_gs[:plot_length],
                    label='$N_0$={} $\Gamma$={:.2g}kHz $t_{{stop}}$={:.2g}$t_0$'
                    .format(
                        N_list[i], dvr.VI * dvr.V0_SI / dvr.kHz_2p,
                        float(dvr.stop_time /
                              get_stop_time(np.array([dvr.freq])))))
                if fit:
                    axs[0].semilogy(
                        data[i].t[:plot_length],
                        fit_fun(data[i].t[:plot_length],
                                *popt,
                                rvs_flg=rvs_flag),
                        '--',
                        label='fitting $N_0$={} $\Gamma$={:.2g}kHz'.format(
                            N_list[i], dvr.VI * dvr.V0_SI / dvr.kHz_2p),
                        lw=3)
                # axs[0].set_ylim([0.9, 1.1])
        # if fit:
        #     left, bottom, width, height = [0.3, 0.6, 0.2, 0.2]
        #     ax2 = subfigs[fi].add_axes([left, bottom, width, height])
        #     ax2.plot(N_list, lifetime)
        #     ax2.set_xlabel('N')
        #     ax2.set_ylabel('$\\tau/s$')
        #     ax2.set_title('Lifetime')
        axs[0].set_title(dvr.title1)
        if first_fig:
            axs[0].axhline(y=1 / np.e, color='gray', label='$\\rho=1/e$')
            axs[0].grid()
        axs[0].legend()
        # plt.savefig('3D_{}.png'.format(model))
        axs[0].set_xlabel(dvr.xlabel)
        axs[0].set_ylabel('$\\rho$')
        if avg:
            axs[2].legend()
            axs[2].set_xlabel(dvr.xlabel)
            axs[2].set_title(dvr.title2)
        ax_list.append(axs)
    plt.savefig('{}d_{}.jpg'.format(dvr.dim, dvr.quantity))
    return fig


def get_data(N_list, R0_list, dvr: plot, t_step):
    fn = lambda i: dvr.filename_gen(N_list, R0_list, t_step, i)
    data = []
    for i in range(len(N_list)):
        io = Output(wavefunc=dvr.wavefunc)
        io.read_file(fn(i))
        data.append(io)
        if dvr.quantity == 'trap':
            data[i].rho_gs = data[i].rho_trap
            data[i].rho_trap = None
    return data


def moving_avg(rho_gs, rho_avg, avg_no):
    # Calculate the moving time-averaged quantities as an array form
    rho_avg = np.append(rho_avg, np.mean(rho_gs[-avg_no:]))
    return rho_avg


def plot_lifetime(N_list,
                  R0_list,
                  dvr: plot,
                  fig=None,
                  file=False,
                  length=1,
                  err=False,
                  avg_no=10,
                  tau=np.inf,
                  extrapolte=None):

    N_list = list(N_list)
    lt_vs_freq = np.array([]).reshape(0, len(N_list))

    if err:
        lt_err = [lt_vs_freq, lt_vs_freq]

    fn = 'tau %gd %.1f.csv' % (dim, tau)
    if file:
        no_file = False
        try:
            sav = np.loadtxt(fn, delimiter=',')
        except:
            no_file = True
    else:
        no_file = True

    for fi in range(dvr.freq_list_len):
        t_step = dvr.set_each_freq(fi)

        # NORMAL WAIST
        dvr.VI *= dvr.V0_SI / dvr.kHz_2p
        dvr.V0_SI = 104.52 * dvr.kHz_2p * hb  # 104.52kHz * h, potential depth, in SI unit, since hbar is set to 1 this should be multiplied by 2pi
        dvr.w = 1E-6 / a0  # ~1000nm, waist length, in unit of Bohr radius
        dvr.VI *= dvr.kHz_2p / dvr.V0_SI

        # TODO: CHECK IF R AND L VARYING WITH W CAUSES THE DIFFERENCE ON THE LIFETIME
        lt_vs_freq = tau_from_waist(N_list, R0_list, dvr, t_step, avg_no, tau,
                                    length, no_file, lt_vs_freq)

        if err:
            # TIGHTEST WAIST
            dvr.VI *= dvr.V0_SI / dvr.kHz_2p
            dvr.V0_SI = 76 * dvr.kHz_2p * hb  # trap depth for tightest waist
            dvr.w = 8.61E-7 / a0  # tightest waist length
            dvr.VI *= dvr.kHz_2p / dvr.V0_SI

            lt_err[0] = tau_from_waist(N_list, R0_list, dvr, t_step, avg_no,
                                       tau, length, no_file, lt_err[0])

            # FATTEST WAIST
            dvr.VI *= dvr.V0_SI / dvr.kHz_2p
            dvr.V0_SI = 156 * dvr.kHz_2p * hb  # trap depth for fattest waist
            dvr.w = 1.18E-6 / a0  # fattest waist length
            dvr.VI *= dvr.kHz_2p / dvr.V0_SI

            lt_err[1] = tau_from_waist(N_list, R0_list, dvr, t_step, avg_no,
                                       tau, length, no_file, lt_err[1])

    if no_file:
        sav = np.concatenate((dvr.freq_list[:, None], lt_vs_freq), axis=1)
        np.savetxt(fn, sav, delimiter=',')

    fmt = 'o-'
    first_fig = False
    if fig == None:
        fig = plt.figure(figsize=[8, 6])
        ax = fig.add_subplot()
        first_fig = True
        # fmt = 'o-'
    else:
        ax = fig.axes[0]
        # fmt = 's-.'

    if extrapolte != None and isinstance(extrapolte, int):
        Nmin = extrapolte
        ext_lt = np.array([]).reshape(0, 2)
        inset = True
        for i in range(sav.shape[0]):
            fit_x = 1. / np.array(N_list[Nmin:])
            fit_y = sav[i, 1:][Nmin:]
            ##### POLY FIT
            # fit = np.polyfit(np.log(fit_x), np.log(fit_y), 1)
            # p = np.poly1d(fit)
            ##### EXP FIT
            # fit_func = lambda x, a, b: a * np.exp(x * b)
            # popt, pcov = curve_fit(fit_func, fit_x, fit_y)
            # p = lambda x: fit_func(x, *popt)
            # ext = np.array([p(0), abs(p(0) - fit_y[-1])])[None]
            #### USE LAST DATAPOINT
            ext = np.array([fit_y[-1], abs(fit_y[-1] - fit_y[-2])])[None]
            ext_lt = np.append(ext_lt, ext, axis=0)
            # if sav[i, 0] >= 220 and inset:
            #     f2 = plt.figure()
            #     ax2 = f2.add_subplot()
            #     # inset = False
            #     # ax2 = inset_axes(ax, width=1.3, height=0.9, loc=4)
            #     ax2.semilogy(1 / np.array(N_list), sav[i, 1:], '.')
            #     x = np.linspace(0, 1 / 15.)
            #     # ax2.semilogy(x, np.exp(p(np.log(x))), '-')
            #     ax2.semilogy(x, p(x), '-')
            #     ax2.grid()
            #     ax2.set_xlabel('1/N')
            #     ax2.set_ylabel('$\\tau/s$')
            #     ax2.set_title('FSS f=%dkHz w/ ' % sav[i, 0] + dvr.cvg_str)
            #     f2.savefig('{}d_{}_{}_fss.jpg'.format(dvr.dim, dvr.cvg,
            #                                            sav[i, 0]))
        ax.errorbar(sav[:, 0],
                    ext_lt[:, 0],
                    yerr=ext_lt[:, 1],
                    fmt=fmt,
                    label='{}D {} extrapolated $\Gamma$={:.2g}kHz'.format(
                        dvr.dim, dvr.quantity,
                        dvr.VI * dvr.V0_SI / dvr.kHz_2p))
    for ni in range(len(N_list)):
        if dvr.cvg == 'N':
            cvg_str = ' $N_0$={} '.format(N_list[ni])
        elif dvr.cvg == 'R':
            cvg_str = ' $R_0$={}w '.format(N_list[ni] * dvr.dx[:dvr.dim])
        if err:
            ax.fill_between(
                dvr.freq_list.reshape(-1),
                lt_err[0][:, ni],
                lt_err[1][:, ni],
                # interpolate=True,
                alpha=0.3)
        ax_label = '{}D {}'.format(dvr.dim, dvr.quantity) + cvg_str
        if dvr.smooth:
            ax_label += 'smooth'
        # ax_label += '$\Gamma$={:.2g}kHz'.format(dvr.VI * dvr.V0_SI /
        #                                         dvr.kHz_2p)
        # + ' L={:.2g}w'.format(dvr.L)
        # + ' $t_{{stop}}$={:.2g}$t_0$'.format(
        #     float(dvr.stop_time /
        #           get_stop_time(np.array([dvr.freq_list[-1]]))))
        ax.semilogy(sav[:, 0], sav[:, ni + 1], fmt, label=ax_label)
    # ax.set_ylim([0, 30])
    if first_fig:
        if tau < np.inf:
            ax.axhline(y=tau, color='gray', label='$\\tau=%.2fs$' % tau)
        if dvr.dim == 3:
            ax = expt_data(ax)
            ax = fgr(ax)
        ax.grid(visible=True)
        ax.set_xlabel('freq/kHz')
        # ax.set_ylabel('$\\rho$')
        ax.set_ylabel('$\\tau/s$')
        # ax.set_ylim([.3, 20])
        # ax.set_xlim([0, 1000])
        ax.set_xlim([80, 250])

    ax.legend()
    # ax.set_title('Saturation value of {}D {:g}s-averaged {} GS population @ \n\
    # stop time {:g}s '.format(dim, 16 * avg_no / step_no *
    #                  stop_time, model, stop_time) + final_str)
    ax.set_title(
        'Lifetime of {}D {} {} @'.format(dvr.dim, dvr.model, dvr.quantity) +
        ' ' + dvr.cvg_str)
    # else:
    #     ax.set_title('Lifetime of {}D {}\ncompared w/ exp\'t @'.format(
    #         dvr.dim, dvr.model) + ' $R_0$={}w'.format(R0_list[0][:dim]))
    # ax.set_title(
    #     'Lifetime of 3D {} GS\n with $\\tau_{{eff}}$ vs w/o $\\tau_{{eff}}$ @'.
    #     format(model) + ' $R_0$={}w'.format(R0 / w))
    # print(freq_list[:, None] * freq_SIunit)
    # print(lt_vs_freq)
    # return freq_list[:, None] * freq_SIunit, lt_vs_freq
    fig.savefig('{}d_{}_{}_lt.pdf'.format(dvr.dim, dvr.cvg, dvr.quantity))
    return fig


def tau_from_waist(N_list, R0_list, dvr: plot, t_step, avg_no, tau, length,
                   no_file, lt_vs_freq) -> np.ndarray:
    if avg_no == 0:
        avg_no = 10
        avg = False
    else:
        avg = True

    dvr.set_all_n(N_list, R0_list, avg_no, avg)

    if no_file:
        lt_vs_freq = get_tau(N_list, R0_list, dvr, avg_no, tau, lt_vs_freq,
                             t_step, length)
    return lt_vs_freq


def get_tau(N_list,
            R0_list,
            dvr: plot,
            avg_no,
            tau,
            lt_vs_freq,
            t_step,
            length=1):
    data = get_data(N_list, R0_list, dvr, t_step)

    final_val = np.array([])
    lifetime = np.array([])
    for i in range(len(N_list)):
        final_val = moving_avg(data[i].rho_gs, final_val, 16 * avg_no)
        lifetime, __, __ = fit_tau(lifetime, data[i], tau, length)

    # sat_freq = np.append(sat_freq, final_val[None], axis=0)
    lt_vs_freq = np.append(lt_vs_freq, lifetime[None], axis=0)
    return lt_vs_freq


def fit_tau(lifetime, data, tau=np.inf, length=1):
    def ognl_fit_fun(x, b):
        return fit_fun(x, b, rvs_flg=False)

    def rvs_fit_fun(x, b):
        return fit_fun(x, b, rvs_flg=True)

    fit_x = data.t.reshape(-1)
    fit_length = int(fit_x.shape[0] / length)
    fit_x = fit_x[:fit_length]
    fit_y = data.rho_gs.reshape(-1)[:fit_length]
    rvs_flag = False

    popt, pcov = curve_fit(ognl_fit_fun, fit_x, fit_y, bounds=(1E-5, 1E6))
    # print('popt =', popt[0])
    # print('pcov =', pcov[0][0])
    if pcov[0][-1] < np.inf:
        lifetime = np.append(lifetime, 1 / (1 / tau + 1 / popt[-1]))
    else:
        rvs_flag = True
        popt, pcov = curve_fit(rvs_fit_fun, fit_x, fit_y, bounds=(1E-10, 1))
        lifetime = np.append(lifetime, 1 / (1 / tau + popt[-1]))
    return lifetime, popt, rvs_flag


def expt_data(ax: plt.Axes):
    strobe = np.array([300, 200, 400, 150, 175])
    lifetime = np.array([9.89, 7.01, 9.4, .363, 2.93])
    ub = np.array([12.6, 7.54, 11, .409, 3.81])
    err = ub - lifetime

    strobe2 = np.array([175, 160, 300, 500, 1000, 750, 250, 0])
    lifetime2 = np.array([2.66, .844, 11.2, 9.07, 6.44, 15.1, 14.8, 17.9])
    ub2 = np.array([3.02, .866, 12.1, 9.81, 6.56, 15.6, 18.2, 19])
    err2 = ub2 - lifetime2

    strobe3 = np.array([750])
    lifetime3 = np.array([14.6])
    ub3 = np.array([17])
    err3 = ub3 - lifetime3

    ax.errorbar(strobe, lifetime, yerr=err, fmt='v', label='exp\'t 12/12')
    ax.errorbar(strobe2, lifetime2, yerr=err2, fmt='v', label='exp\'t 12/13')
    ax.errorbar(strobe3, lifetime3, yerr=err3, fmt='v', label='exp\'t 12/14')
    # ax.set_yscale('log', nonposy='clip')
    return ax


def fgr(ax: plt.Axes) -> plt.Axes:
    w = 1E-6
    m = 6.015122 * 1.66E-27
    h = 6.626E-34
    hb = h / (2 * np.pi)
    f = 2 * np.pi * np.array([26.22, 26.22, 4.6]) * 1E3
    fm = gmean(f)
    V = 104.52E3 * 2 * np.pi
    hl = np.sqrt(hb / (m * fm))
    leff2 = 1 / (4 / w**2 + 1 / hl**2)
    Eg = np.sum(f) / 2 - V

    def fgr_func(freq):
        omega = 2 * np.pi * freq * 1E3
        tau = 2 * np.pi * hl / (2 * V**2 * leff2) * np.sqrt(
            h * (omega + Eg) / m) * np.exp(m * omega * leff2 / hb)
        return tau

    x = np.linspace(100, 240)
    ax.plot(x, fgr_func(x), label='FGR')
    return ax


def plot_wavefunction(N_list, R0_list, dvr: plot, length=1):

    N_list = list(N_list)
    dvr.wavefunc = True
    p = 0
    if dvr.symmetry:
        p = 1

    for fi in range(dvr.freq_list_len):
        t_step = dvr.set_each_freq(fi)
        dvr.set_all_n(N_list, R0_list, 0, False)
        fn = lambda i: dvr.filename_gen(N_list, R0_list, i, t_step)

        for i in range(len(N_list)):
            io = Output(wavefunc=dvr.wavefunc)
            io.read_file(fn(i))

            dx = dvr.dx_list[i][0]
            dvr.update_R0(R0_list[i])
            R = dvr.R[0]
            R0 = dvr.R0[0]
            t_len = int(len(io.t) / length)
            n_period = int(io.t[t_len - 1] / dvr.T)

            x = np.linspace(-R, R, int(1000))[:, None]
            psi_xt = psi(dvr.n_list[i], dx, io.psi[:t_len, :].T, x, p)
            psi_xt = abs(psi_xt)**2
            X, T = np.meshgrid(x.reshape(-1) / R0,
                               io.t.reshape(-1)[:t_len],
                               indexing='ij')
            fig = plt.figure(figsize=[6 * 2, 5])
            sf = fig.subfigures(1, 2)
            ax = sf[0].subplots()
            pcm = ax.pcolormesh(X,
                                T,
                                psi_xt,
                                label='$N_0$={}'.format(N_list[i]),
                                norm=colors.LogNorm(vmin=1E-8,
                                                    vmax=psi_xt.max()))
            fig.colorbar(pcm, ax=ax)
            ax.set_xlabel('x/R')
            ax.set_ylabel('t/s')
            for i in range(1, n_period + 1, 1):
                ax.axhline(y=i * dvr.T, color='gray')
            ax.axvline(x=-1, color='w')
            ax.axvline(x=1, color='w')
            gs = sf[1].subplots()
            ab_str = '$\Gamma$={:.2f}kHz'.format(dvr.VI * dvr.V0_SI /
                                                 dvr.kHz_2p)
            final_str = 'freq={:.3f}kHz '.format(
                dvr.freq) + dvr.cvg_str + ' ' + ab_str
            ax.set_title('{}D {} GS probability @ \n\
                    stop time {:.2g}s '.format(dvr.dim, dvr.model,
                                               dvr.stop_time) + final_str)

            for i in range(5):
                slc = int(i / 5 * X.shape[1])
                gs.plot(X[:, slc],
                        psi_xt[:, slc],
                        label='t={:.2g}s'.format(T[0, slc]))
            gs.legend()
            gs.set_xlabel('x/R')
            gs.set_ylabel('$\\rho$')
            gs.set_title('{}D {} probabilities @ '.format(dvr.dim, dvr.model) +
                         dvr.cvg_str + ' ' + ab_str)
        plt.savefig('{}d_wavefunc_{:.2f}_{:.2f}.jpg'.format(
            dvr.dim, dvr.freq, dvr.VI * dvr.V0_SI / dvr.kHz_2p))

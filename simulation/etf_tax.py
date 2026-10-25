"""German tax bookkeeping for the ETF simulation. Illustrative, not tax advice.

Everything is vectorised over simulation paths (numpy arrays with one entry per path).
"""
import numpy as np


def apply_tax(taxable, allowance_left, loss_pot, rate):
    """Tax on taxable gains, using the loss pot first and then the yearly allowance.

    taxable          gains after the 30% exemption; negative means a loss
    allowance_left   tax-free allowance still unused this year
    loss_pot         losses carried forward from earlier sales
    Returns the tax, the allowance left and the loss pot after this transaction.
    """
    gain = np.maximum(taxable, 0.0)
    loss_pot = loss_pot + np.maximum(-taxable, 0.0)
    use_loss = np.minimum(loss_pot, gain)
    gain = gain - use_loss
    loss_pot = loss_pot - use_loss
    use_allowance = np.minimum(allowance_left, gain)
    gain = gain - use_allowance
    return rate * gain, allowance_left - use_allowance, loss_pot


def vorabpauschale(value_at_year_start, growth_factor, basiszins, fraction):
    """Vorabpauschale per fund: 70% of the base rate times the opening value, capped at the
    fund's actual gain over the year (growth_factor is the year's growth, 1.10 = +10%)."""
    basisertrag = fraction * basiszins * value_at_year_start
    actual_gain = np.maximum(value_at_year_start * (growth_factor - 1.0), 0.0)
    return np.minimum(basisertrag, actual_gain)

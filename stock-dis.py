#!/usr/bin/python3
"""
Distribution of performance for investments done over a fixed period of time.
The plots show a distribution of every possible investment over a fixed period of time.
This distribution shows a perspective that is useful for long-time investment and shows
what the ROI has been for every investment (purchase and sell) that has lasted exactly M months.

@author: Sebastian Palacio
@email: spalaciob [at] gmail [dot] com
"""
import os
import sys
import argparse
import traceback
import matplotlib.pyplot as plt


def fetch_data(stock_input, drop_points=0):
  """Retrieves structured data about the historical performance of a stock
  
  @param stock_input: str. File path with asset_prices separated by TABS. Format is:
    Month Day, Year [TAB] Open [TAB] High [TAB] Low Close* [TAB] Adj Close** [TAB] Volume
    Data is assumed to be sorted chronologically, with the most recent asset_prices first.
  
  @param drop_points: int. Ignore these many samples at the beginning of the file.
    Useful to ignore historical data that goes too far back in the past.

  @return: (list, str0, str1). List of float asset_prices corresponding to the stock price
    between the dates str0, and str1.
  """
  asset_prices = []
  min_date = ''
  max_data = ''
  with open(stock_input) as file_in:
    for line in file_in.readlines()[-drop_points-1::-1]:
      line_values = line.strip().split('\t')
      # skip lines that are not well-formed (e.g., dividents or stock splits)
      if len(line_values) > 2:
        asset_prices.append(float(line_values[-2].replace(',', '')))
        if min_date == '':
          min_date = line_values[0]
        max_date = line_values[0]
  return asset_prices, min_date, max_date


def asset_growth(prices_over_time, t=12):
  """Calculates the ratio of growth (sell_price/purchase_price) for all possible `t` periods.
  In other words, how much did the price fluctuated after `t` units of time.
  Takes the ratio between positions prices_over_time[i] and prices_over_time[i+t]

  @param prices_over_time: list of floats. Price of the stock or index over time.

  @param t: int. Number of time steps to calculate the asset growth over.
    Each entry on `prices_over_time` is considered a time-step.

  @return: list of floats. All possible ratios of growth made over `t` time intervals.
  """
  growth_ratios = []
  for purchase_idx, purchase_price in enumerate(prices_over_time[:-t]):
    sell_price = prices_over_time[purchase_idx+t]
    growth_ratios.append(sell_price/purchase_price)
  return growth_ratios


def compound(principal, rate, num_compound, time):
    """Calculate compound interest on a given principal over time
    
    @param principal: float. Initial amount of money
    @param rate: float. Expected rate at which money is compounding every time.
    @param num_compound: int. Number of time steps after which compounding is applied.
    @param time: int. Total number of time steps over which compounding happens.

    @return: float. Value of the principal after compounding over `time` time. 
    """
    return principal*(1 + rate/num_compound)**(num_compound*time)


def plot_performance_distribution(ratios_over_time, price_idx, asset_name, cpi=-1, min_date='', max_date='', logy=False):
  """Draw and save the distribution of growth.

  @param ratios_over_time: list of lists of floats.
    Each nested list has all growth ratios of growth made over `t` time intervals, where `t`
    is the index of the main list.

  @param price_idx: list of floats. Estimated CPI after `t` years. Samples below this point are loosing in value
    even if they are higher than the original purchase value (because of inflation).

  @return: None.
  """
  _ = plt.figure(figsize=(15, 8))
  plt.plot(range(1, len(ratios_over_time)+1), [1] * len(ratios_over_time), 'g-')
  plt.plot(range(1, len(ratios_over_time)+1), price_idx, 'r--', alpha=0.5, label=f'CPI ({cpi}% p.a.)')
  plt.violinplot(ratios_over_time)
  plt.boxplot(ratios_over_time, sym='k.')
  plt.xlabel('Investment duration (years)\n' + 
    'Source: Adjusted close price; adjusted for splits ' + 
    'and dividend and/or capital gain distributions.')
  plt.ylabel('RoI distribution')
  plt.title(f'{asset_name.upper()} performance\n({min_date} - {max_date})')
  if logy:
    plt.gca().set_yscale('log')
  plt.grid(axis='y')
  plt.legend()

  plt.savefig(f'roi_dist_{asset_name}.pdf')
  print(f'Saved to "roi_dist_{asset_name}.pdf"')


def time_to_catch_up_cpi(ratios_over_time, price_idx, asset_prices):
  """For time intervals that end up underperforming the CPI, lookup into the future and estimate
  how much longer it would have taken to catch up (if at all) with CPI.

  @param ratios_over_time: list of lists of floats.
    Each nested list has all growth ratios of growth made over `t` time intervals, where `t`
    is the index of the main list.

  @param price_idx: list of floats. Estimated CPI after `t` years. Samples below this point are loosing in value
    even if they are higher than the original purchase value (because of inflation).

  @param asset_prices: list of floats. Price of the stock or index over time.

  @return: list of lists of floats, list of list of floats. Each nested list has underperforming investments
    over a constant period of time. The values correspond to how many years it took for those investments to
    catch up to (first list) or get the highest (second list) CPI.
  """
  recover_times = []
  non_recovery = []
  for time_interval, (growth_ratios, cpi) in enumerate(zip(ratios_over_time, price_idx), start=1):
    recover_times.append([])
    non_recovery.append([])
    for purchase_idx, growth_ratio in enumerate(growth_ratios):
      if growth_ratio < cpi:
        purchase_price = asset_prices[purchase_idx]
        
        # Lookup the remaining development of the price asset until it reaches a growth_ratio that
        # exeeds the corresponding CPI
        recovery_months = 0
        for months, rest_value in enumerate(asset_prices[purchase_idx + 12*time_interval:], start=1):
          longer_investment_growth = rest_value / purchase_price
          if longer_investment_growth > growth_ratio:
            growth_ratio = longer_investment_growth
            recovery_months = months
            # TODO: as a more rigurous criterion, compare growth_ratio with CPI of the *next* year before breaking
            try:
              future_cpi = price_idx[time_interval+1+recovery_months//12]
            except IndexError:
              # Growth ratio improved but did not exceed CPI
              non_recovery[-1].append(recovery_months/12)
              break
            
            if growth_ratio >= future_cpi:
              # Found the smallest interval after which the asset purchase caught up with the CPI.
              recover_times[-1].append(recovery_months/12)
              break   
        else:
          # growth_ratio did not improve even after extending the time it remained invested
          non_recovery[-1].append(recovery_months/12)
  return recover_times, non_recovery


def plot_recovery_distribution(recover_times, non_recovery, asset_name):
  """Draw and save the distribution of recovery times.

  @param recover_times: list of lists of floats. Each nested list has the amount of time (in years)
    that underperforming investments (initially made over a fixed `t` time interval) needed to catch
    up with CPI. `t` is the index of the main list.

  @param non_recovery: list of lists of floats. Each nested list has the amount of time (in years)
    that underperforming investments (initially made over a fixed `t` time interval) needed to get the
    closest to CPI (without catching up). `t` is the index of the main list.

  @return: None.
  """
  _ = plt.figure()
  
  # Plot distribution of samples that did recover
  nz_recover_times = [i+1 for i in range(len(recover_times)) if len(recover_times[i]) > 0]
  if len(nz_recover_times) > 0:
    plt.violinplot([recover_times[nz-1] for nz in nz_recover_times], positions=nz_recover_times)
    plt.boxplot([recover_times[nz-1] for nz in nz_recover_times], positions=nz_recover_times, sym='k.')

  # Plot distribution of samples that did not recover
  nz_non_recovery = [i+1 for i in range(len(non_recovery)) if len(non_recovery[i]) > 0]
  if len(nz_non_recovery) > 0:
    violins = plt.violinplot([non_recovery[nz-1] for nz in nz_non_recovery], positions=nz_non_recovery)
    _ = [v.set_facecolor('red') for v in violins['bodies']]
  
  plt.xlabel('time in the market (years)')
  plt.ylabel('extra time until beating CPI (years)')
  plt.grid()
  
  plt.savefig(f'roi_{asset_name}_recovery.pdf')
  print(f'Saved to "roi_{asset_name}_recovery.pdf"')


def main(opts):
  # Load
  asset_name = os.path.basename(opts.infile).split('.')[0]
  asset_prices, min_date, max_date = fetch_data(opts.infile, opts.drop_points)

  # Populate Data (assumes monthly asset prices)
  ratios_over_time = []
  price_idx = []  # expected consumer price index (devaluation of money)
  for num_years in range(1, min(opts.num_years, len(asset_prices)//12)):
    ratios_over_time.append(asset_growth(asset_prices, t=12*num_years))
    price_idx.append(compound(1, opts.cpi/100, 1, num_years))

  # Plot
  _ = plot_performance_distribution(
    ratios_over_time, 
    price_idx, 
    asset_name, 
    opts.cpi, 
    min_date, 
    max_date, 
    opts.logy)
  
  # For time intervals that end up underperforming the CPI, plot how long it took to catch up (if at all)
  if opts.recovery:
    recover_times, non_recovery = time_to_catch_up_cpi(ratios_over_time, price_idx, asset_prices)
    _ = plot_recovery_distribution(recover_times, non_recovery, asset_name)

  if not opts.silent:
    plt.show()


if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument(
    '-i',
    '--input',
    metavar='FILE',
    dest='infile',
    required=False,
    default='data/snp500.txt',
    help='Input file (TXT) from Yahoo Finance')
  parser.add_argument(
    '-y',
    '--num_years',
    metavar='YEARS',
    required=False,
    type=int,
    default=10,
    help='Up to how many years shall distributions be plotted.')
  parser.add_argument(
    '-p',
    '--cpi',
    metavar='PERCENTAGE',
    required=False,
    type=float,
    default=2.0,
    help='Average consumer price index (single value). ' + 
          'For germany has been 2.1, for the EU is 3.94 and for the world is 5.55')
  parser.add_argument(
    '-s',
    '--silent',
    required=False,
    default=False,
    action='store_true',
    help='Supress interactive plot'
  )
  parser.add_argument(
    '-l',
    '--logy',
    required=False,
    default=False,
    action='store_true',
    help='Plot Y-axis in log-scale'
  )
  parser.add_argument(
    '-d',
    '--drop_points',
    required=False,
    metavar='POINTS',
    type=int,
    default=0,
    help='Ignore the first POINTS points (in months).'
  )
  parser.add_argument(
    '-R',
    '--recovery',
    required=False,
    action='store_true',
    default=False,
    help='For time intervals that underperform wrt CPI, plot distribution of "time until they recover".'
  )

  opts = parser.parse_args(sys.argv[1:])

  try:
    main(opts)
  except Exception:
    print('Unhandled error!')
    traceback.print_exc()
    sys.exit(-1)
  finally:
    print('All Done')

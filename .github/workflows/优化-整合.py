import tushare as ts
import pandas as pd
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
from openpyxl import Workbook

# 设置 Tushare API Token
ts.set_token('4ddcd201218795e3e6133c091cbddcc64e72961017422eac6d993e01')  # 替换为你的 Tushare API Token
pro = ts.pro_api()


def fetch_all_stock_codes():
    """获取所有 A 股的股票代码"""
    stock_info = pro.stock_basic(exchange='', list_status='L', fields='ts_code,name,market')
    return stock_info['ts_code'].tolist()


def fetch_stock_prices(ts_code, start_date, end_date):
    """获取单只股票的历史价格数据"""
    try:
        df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        return df[['ts_code', 'trade_date', 'close']].sort_values(by='trade_date')  # 按交易日期排序
    except Exception as e:
        print(f"Error fetching stock price data for {ts_code}: {e}")
        return pd.DataFrame()


def fetch_stock_pe(ts_code, start_date, end_date):
    """获取单只股票的市盈率数据"""
    try:
        df = pro.fina_indicator(ts_code=ts_code, fields='ts_code,end_date,pe_ttm')
        df.rename(columns={'end_date': 'trade_date'}, inplace=True)  # 统一日期字段名称
        df['trade_date'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y%m%d')  # 确保日期格式一致
        return df[['ts_code', 'trade_date', 'pe_ttm']].sort_values(by='trade_date')
    except Exception as e:
        print(f"Error fetching PE data for {ts_code}: {e}")
        return pd.DataFrame()


def compute_rsi(data, period):
    """计算 RSI 指标"""
    if len(data) < period:  # 数据不足，无法计算 RSI
        return pd.Series([None] * len(data), index=data.index)

    delta = data['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def save_to_excel(data_dict, output_file):
    """将所有股票的数据保存到 Excel 文件"""
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        for ts_code, df in data_dict.items():
            if not df.empty:
                df.to_excel(writer, sheet_name=ts_code[:31], index=False)  # 仅保留前 31 个字符作为 sheet 名
    print(f"数据已保存到 {output_file}")


def main():
    # 计算时间范围
    today = datetime.today().date()
    end_date = (today + relativedelta(days=1)).strftime('%Y%m%d')
    start_date_obj = datetime.strptime(end_date, '%Y%m%d').date() - relativedelta(years=2)
    start_date = start_date_obj.strftime('%Y%m%d')

    # 文件路径
    output_file_all = r"D:\投资理财\A股价格与市盈率数据.xlsx"  # 原始数据文件
    output_file_filtered = r"D:\投资理财\filtered_file.xlsx"  # 筛选后的数据文件

    # 获取所有 A 股股票代码
    stock_codes = fetch_all_stock_codes()

    # 存储所有股票数据
    all_stocks_data = {}  # 原始数据
    filtered_stocks_data = {}  # 筛选后数据

    # 遍历所有股票
    for ts_code in stock_codes:
        print(f"Fetching data for {ts_code}...")

        # 获取股价和市盈率数据
        prices_df = fetch_stock_prices(ts_code, start_date, end_date)
        pe_df = fetch_stock_pe(ts_code, start_date, end_date)

        if prices_df.empty or pe_df.empty:
            continue  # 如果数据缺失，则跳过

        # 合并股价和市盈率
        merged_df = pd.merge(prices_df, pe_df, on=['ts_code', 'trade_date'], how='left')

        # 计算 RSI(6)、RSI(14)、RSI(21)
        merged_df['RSI_6'] = compute_rsi(merged_df, period=6)
        merged_df['RSI_14'] = compute_rsi(merged_df, period=14)
        merged_df['RSI_21'] = compute_rsi(merged_df, period=21)

        # 存储完整数据
        all_stocks_data[ts_code] = merged_df

        # 取最新一天的数据
        last_row = merged_df.iloc[-1]
        last_rsi_6 = last_row['RSI_6']
        last_pe = last_row.get('pe_ttm', None)
        last_close = last_row.get('close', None)

        # 筛选条件（只根据 RSI(6) ≤ 30）
        if last_rsi_6 is not None and last_rsi_6 <= 30:
            filtered_stocks_data[ts_code] = merged_df  # 存入筛选数据

        # 避免 API 频率限制
        time.sleep(0.5)

    # 保存原始数据和筛选数据
    save_to_excel(all_stocks_data, output_file_all)
    save_to_excel(filtered_stocks_data, output_file_filtered)


# 执行主函数
if __name__ == "__main__":
    main()

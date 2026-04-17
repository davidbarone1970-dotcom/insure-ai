import traceback
try:
    import main
    print('OK')
except Exception as e:
    traceback.print_exc()

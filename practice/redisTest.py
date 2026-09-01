import redis # redis lib

#create a client --> server running at port=6379 with decoderesponses = true
r = redis.Redis(host = "localhost", port = 6379, decode_responses=True)

#INCR --> atomic increment command
#if the key doesnt exist yet --> redis treats it as starting at 0
#this call creates and increments to 1 the first time its used
r.incr("test_counter")

#GET --> read the current value back
value = r.get("test_counter") 

print(f"counter is now: {value}")


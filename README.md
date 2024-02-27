# hfss-proxy-script
Python script to connect HFSS to System Coupling

Currently, the script assumes two regions, "Die1" and "Die2" that
can exchange volume loss density and temperature with another solver.

They also require two files "Die1.pts" and "Die2.pts" to contain
point coordinates, separated by spaces.

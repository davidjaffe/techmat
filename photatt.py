#!/usr/bin/env python
'''
calculate photon attenuation of tech mat setup 
disc source ---> pinhole ---> PMT
20141001 units are mm
'''
import math
import sys
import random
import datetime

class photatt():
    def __init__(self):

        self.discRadius = 25./2.
        self.pinhole = [2., 300.] # hole radius, distance from source
        self.PMT     = [25.4, 700.-112.-220.] # PMT radius, distance - PMT height - base height
        D = self.pinhole[1]
        r = self.pinhole[0]+self.discRadius
        ctmin = D/math.sqrt(D*D + r*r)
        self.ctrange = [ctmin, 1.0]
        
        return
    def genAngles(self):
        ctmin,ctmax = self.ctrange
        ct = random.uniform(ctmin,ctmax)
        phi= random.uniform(0.,2.*math.pi)
        return ct,phi
    def genPosition(self):
        r = math.sqrt(random.uniform(0.,self.discRadius*self.discRadius))
        az = random.uniform(0.,2.*math.pi)
        return r,az
    def shoot(self,point=True):
        goal = [False, False]
        hits = []
        ct,phi = self.genAngles()
        st = math.sqrt(1.-ct*ct)
        if point:
            x0, y0 = 0.,0.
        else:
            r,az   = self.genPosition()
            x0 = r*math.cos(az)
            y0 = r*math.sin(az)
        hits.append( [x0, y0] )
        z0 = 0.
        # does photon pass thru pinhole?
        z1 = self.pinhole[1]
        s = (z1-z0)/ct
        x1 = x0 + s*st*math.cos(phi)
        y1 = y0 + s*st*math.sin(phi)
        if x1*x1+y1*y1 < self.pinhole[0]*self.pinhole[0] : goal[0] = True
        hits.append( [x1, y1] )
        # thru pinhole, does photon hit PMT
        z1 = z1 + self.PMT[1]
        s = (z1-z0)/ct
        x1 = x0 + s*st*math.cos(phi)
        y1 = y0 + s*st*math.sin(phi)
        if x1*x1+y1*y1 < self.PMT[0]*self.PMT[0] : goal[1] = True
        hits.append( [x1, y1] )
        return goal, hits
if __name__ == '__main__' :
    ph = photatt()
    fn = '/Users/djaffe/work/paw/TECHMAT/photatt'
    unique = '_{0}'.format(datetime.datetime.now().strftime("%Y%m%d%H%M_%f"))
    fn += unique + '.nt'
    f = open(fn,'w')
    point = False
    n = 1000000
    good = [0,0]
    for i in range(n):
        goal,hits = ph.shoot(point=point)
        if goal[0] : good[0] += 1
        if goal[0] and goal[1] : good[1] += 1
        s = str(float(point))
        for g in goal : s += ' ' + str(float(g))
        for p in hits : s += ' ' + str(p[0]) + ' ' + str(p[1])
        s += ' \n'
        f.write(s)
    f.close()
    print 'wrote',fn
    for g in good:
        ratio = float(g)/float(n)
        a = abs(ph.ctrange[0]-ph.ctrange[1])/2
        print 'good',g,'n',n,'ratio',ratio,'a',a,'a*ratio',a*ratio
    print 'illumination is point?',point,'disc radius',ph.discRadius,'(mm)'
    print 'pinhole radius',ph.pinhole[0],'(mm) at',ph.pinhole[1],'(mm) from illumination'
    print 'PMT radius',ph.PMT[0],'(mm) at',ph.PMT[1],'(mm) from pinhole'
    

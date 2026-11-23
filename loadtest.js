import http from 'k6/http';
import { check } from 'k6';

export const options = {
  vus: 200, // Number of virtual users
  duration: '20s', // Duration of the test
};

export default function (){
    const id = Math.random() < 0.8 
        ? Math.floor(Math.random() * 100)
        : Math.floor(Math.random() * 500000) ; 9
    
    const res = http.get(`http://localhost:8000/code${id}`, {redirects : 0});
    check(res, {'status is 302' : (r) => r.status === 302});
   
}